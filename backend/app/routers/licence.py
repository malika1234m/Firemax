"""Licensing for the fully-local Home Assistant add-on.

The add-on runs entirely on the customer's hardware and holds no account, so it
cannot authenticate as a user. Entitlement instead travels as an opaque key the
admin copies out of this dashboard, which the add-on checks once and then caches
locally (see ha_agent/licence.py).

Two endpoints, deliberately different in who may call them:

  POST /licence/validate   — PUBLIC. Called by add-ons in the field, which have
                             no session. Rate-limited, because it is an
                             unauthenticated lookup by secret.
  GET  /licence/me         — admin only. Shows the org its own key.
  GET  /licence/me/activations, DELETE /licence/me/activations/{id}
                           — admin only. The installations using the key.

Without a valid key the add-on is not blocked; it drops to a one-camera free
tier. That is a safety decision as much as a commercial one: this software's job
is noticing fires, and an expired card or an unreachable cloud must never be the
reason a building stops being watched.
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.database import get_db
from app.licence_signing import sign_entitlement
from app.models import (FREE_TIER_MAX_CAMERAS, PLAN_LIMITS, LicenceActivationPublic,
                        LicenceCheck, LicenceKeyPublic, LicencePublic, UserPublic)
from app.rate_limit import rate_limiter
from app.security import require_admin

router = APIRouter(prefix="/licence", tags=["licence"])

# Subscription states that entitle a customer to the paid tier. "trialing" is
# included on purpose — a trial that cannot watch the customer's cameras proves
# nothing and sells nothing.
ENTITLED_STATUSES = {"trialing", "active"}

# Prefix makes a stray key recognisable in a log or a support ticket, so it can
# be rotated rather than puzzled over.
KEY_PREFIX = "fmx"


def _new_key() -> str:
    return f"{KEY_PREFIX}_{secrets.token_urlsafe(24)}"


async def _ensure_key(db, org: dict) -> str:
    """Return the org's licence key, minting one on first use.

    Lazy rather than at signup so organizations created before licensing
    existed get a key without a migration.
    """
    key = org.get("licence_key")
    if key:
        return key
    key = _new_key()
    await db.organizations.update_one({"org_id": org["org_id"]},
                                      {"$set": {"licence_key": key}})
    return key


@router.post("/validate", response_model=LicencePublic)
async def validate_licence(body: LicenceCheck,
                           _rl=Depends(rate_limiter(30, 300))):
    """Check a licence key for one installation. Public — add-ons in the field
    have no session.

    Answers the same shape whether the key is unknown, revoked or unpaid: the
    add-on only needs to know how many cameras it may watch, and a caller
    guessing keys should not learn which guesses named a real organization.

    A valid answer carries a signed entitlement bound to `install_id`. Each
    plan allows a fixed number of installations, so a key passed around stops
    working on the extra machines, and the owner can see and remove them.
    """
    key = (body.licence_key or "").strip()
    if not key:
        return LicencePublic(valid=False, reason="No licence key supplied")

    db = get_db()
    org = await db.organizations.find_one({"licence_key": key})
    if not org:
        return LicencePublic(valid=False, reason="Licence key not recognised")

    if org.get("subscription_status") not in ENTITLED_STATUSES:
        return LicencePublic(valid=False, plan="free",
                             organization=org.get("name"),
                             reason="Subscription is not active")

    if not body.install_id:
        # Add-ons before 1.3.0 send no installation id, so they cannot be held
        # to the installation limit. They keep the free tier, never zero.
        return LicencePublic(valid=False, plan="free", organization=org.get("name"),
                             reason="Update the FiremeX add-on to 1.3.0 or later to use this licence")

    plan = org.get("plan", "trial")
    limit = PLAN_LIMITS.get(plan, {}).get("max_installs", 1)
    now = datetime.now(timezone.utc)
    seat = {"org_id": org["org_id"], "install_id": body.install_id}

    # Claim first, then check the place in line. Counting first and inserting
    # second let two new machines checking in at the same moment both see a
    # free seat. The unique (org_id, install_id) index makes the claim atomic
    # per installation; a concurrent duplicate just finds the row that won.
    try:
        await db.licence_activations.insert_one(
            {**seat, "first_seen": now, "last_seen": now, "addon_version": body.addon_version})
        created = True
    except DuplicateKeyError:
        created = False
    activation = await db.licence_activations.find_one(seat)

    if activation.get("removed"):
        return LicencePublic(valid=False, plan="free", organization=org.get("name"),
                             reason="This installation was removed from the licence by its owner")

    # Only the earliest `limit` live installations hold a seat. Checked on EVERY
    # validation, not just the first, so a downgrade (Pro's 5 to Starter's 1)
    # takes effect on the installations beyond the new limit.
    ahead = await db.licence_activations.count_documents({
        "org_id": org["org_id"], "removed": {"$ne": True},
        "$or": [{"first_seen": {"$lt": activation["first_seen"]}},
                {"first_seen": activation["first_seen"], "_id": {"$lt": activation["_id"]}}],
    })
    if ahead >= limit:
        if created:
            # Do not keep a row for a machine that never got a seat: it would
            # otherwise wait in line and take the next one freed.
            await db.licence_activations.delete_one({"_id": activation["_id"]})
        return LicencePublic(
            valid=False, plan="free", organization=org.get("name"),
            reason=(f"This licence is already active on {ahead} installation(s), the "
                    f"limit for the {plan} plan. Remove one under Settings > Add-on Licence Key."))

    if not created:
        await db.licence_activations.update_one(
            {"_id": activation["_id"]},
            {"$set": {"last_seen": now, "addon_version": body.addon_version}})

    # Paid tiers are unlimited; the number rather than the plan name is what the
    # add-on enforces, so plan definitions can change without a new image.
    return LicencePublic(valid=True, plan=plan, max_cameras=None,
                         organization=org.get("name"),
                         entitlement=sign_entitlement(body.install_id, plan, None, org.get("name")))


@router.get("/me/activations", response_model=list[LicenceActivationPublic])
async def my_activations(admin: UserPublic = Depends(require_admin)):
    """Installations currently using the org's key, newest activity first."""
    db = get_db()
    rows = await db.licence_activations.find(
        {"org_id": admin.org_id, "removed": {"$ne": True}}).sort("last_seen", -1).to_list(100)
    return [LicenceActivationPublic(**r) for r in rows]


@router.delete("/me/activations/{install_id}", status_code=204)
async def remove_activation(install_id: str, admin: UserPublic = Depends(require_admin)):
    """Free a seat. The installation is remembered as removed rather than
    deleted, so a machine that still has the key cannot simply re-activate
    itself — it would need the owner to rotate the key and re-add it."""
    db = get_db()
    res = await db.licence_activations.update_one(
        {"org_id": admin.org_id, "install_id": install_id, "removed": {"$ne": True}},
        {"$set": {"removed": True, "removed_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Installation not found")


@router.get("/me", response_model=LicenceKeyPublic)
async def my_licence_key(admin: UserPublic = Depends(require_admin)):
    """The caller's own key, for copying into the add-on's Configuration tab."""
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    key = await _ensure_key(db, org)
    entitled = org.get("subscription_status") in ENTITLED_STATUSES
    return LicenceKeyPublic(
        licence_key=key,
        plan=org.get("plan", "trial"),
        max_cameras=None if entitled else FREE_TIER_MAX_CAMERAS,
    )


@router.post("/me/rotate", response_model=LicenceKeyPublic)
async def rotate_licence_key(admin: UserPublic = Depends(require_admin)):
    """Issue a new key and invalidate the old one.

    The key is a bearer credential pasted into a config field, so it will
    eventually end up in a screenshot or a support thread. Rotation has to be
    self-service or it will not happen.
    """
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    key = _new_key()
    await db.organizations.update_one({"org_id": admin.org_id},
                                      {"$set": {"licence_key": key}})
    # A rotated key is a fresh start: every installation must be given the new
    # key, so the old seats (including any a leaked key had taken) are dropped.
    await db.licence_activations.delete_many({"org_id": admin.org_id})
    entitled = org.get("subscription_status") in ENTITLED_STATUSES
    return LicenceKeyPublic(
        licence_key=key,
        plan=org.get("plan", "trial"),
        max_cameras=None if entitled else FREE_TIER_MAX_CAMERAS,
    )
