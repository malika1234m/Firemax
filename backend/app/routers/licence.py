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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.database import get_db
from app.licence_signing import ENTITLEMENT_SECONDS, sign_entitlement
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

# New installations allowed per entitlement period beyond the plan's seats —
# room to reinstall Home Assistant, not to cycle a key across machines.
SPARE_ACTIVATIONS = 2

# Key replacements per entitlement period that also reset the new-installation
# allowance. Replacing the key itself (revoking the old one) is never refused.
MAX_ROTATIONS = 2


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
    key_gen = org.get("licence_key_gen", 0)

    # Claim first, then check the place in line. Counting first and inserting
    # second let two new machines checking in at the same moment both see a
    # free seat. The unique (org_id, install_id) index makes the claim atomic
    # per installation; a concurrent duplicate just finds the row that won.
    try:
        await db.licence_activations.insert_one(
            {**seat, "first_seen": now, "last_seen": now, "addon_version": body.addon_version,
             "key_gen": key_gen})
        created = True
    except DuplicateKeyError:
        created = False
    activation = await db.licence_activations.find_one(seat)
    if activation is None:
        # A concurrent request for this same installation claimed the row and
        # was turned away over the limit, deleting it in between.
        return LicencePublic(valid=False, plan="free", organization=org.get("name"),
                             reason="Licence check interrupted — it will be retried")

    if created:
        # Seat cycling: activate, remove in the dashboard, activate the next
        # machine. Each removed machine kept its signed licence offline until it
        # expired, so one key could cover many machines. Cap NEW installations
        # per entitlement period at the plan's seats plus two spare, which still
        # covers reinstalling Home Assistant. Removed rows stay on record, so
        # removing does not reset this count. It is counted per key generation:
        # whoever holds a leaked key can use up the old key's allowance, but not
        # the new one's, so rotating stays a working remedy for the owner.
        since = now - timedelta(seconds=ENTITLEMENT_SECONDS)
        # Only rows AHEAD of this one in line count. Counting every recent row
        # let simultaneous new installations each see all the others — still
        # waiting to be turned away — and every one of them was refused,
        # including the one entitled to the seat.
        earlier = await db.licence_activations.count_documents(
            {"org_id": org["org_id"], "first_seen": {"$gte": since},
             # Rows written before key generations existed have no key_gen;
             # they belong to generation 0 and must count, not slip past.
             "key_gen": {"$in": [key_gen, None]} if key_gen == 0 else key_gen,
             "$or": [{"first_seen": {"$lt": activation["first_seen"]}},
                     {"first_seen": activation["first_seen"], "_id": {"$lt": activation["_id"]}}]})
        if earlier >= limit + SPARE_ACTIVATIONS:
            await db.licence_activations.delete_one({"_id": activation["_id"]})
            return LicencePublic(
                valid=False, plan="free", organization=org.get("name"),
                reason=(f"Too many new installations for this licence in the last "
                        f"{ENTITLEMENT_SECONDS // 86400} days. Contact FiremeX support."))

    if activation.get("removed") and activation.get("removed_by") == "rotation":
        # The owner issued a new key and pasted it into this same installation:
        # it rejoins in its old place in line. Only someone holding the NEW key
        # gets here, so this restores a seat the owner meant to keep.
        await db.licence_activations.update_one(
            {"_id": activation["_id"]},
            {"$set": {"removed": False, "key_gen": key_gen},
             "$unset": {"removed_by": "", "removed_at": ""}})
        activation["removed"] = False

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

    # The key may have been replaced while this check was running. Rotation
    # first swaps the key, then marks every installation removed; a seat this
    # request claimed in between would survive that sweep. Re-reading here
    # closes the gap: if the key is still current, the sweep has not started
    # and will catch this row; if it is not, refuse.
    if not await db.organizations.find_one({"org_id": org["org_id"], "licence_key": key},
                                           {"_id": 1}):
        await db.licence_activations.update_one(
            {"_id": activation["_id"]},
            {"$set": {"removed": True, "removed_by": "rotation", "removed_at": now}})
        return LicencePublic(valid=False, reason="Licence key not recognised")

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

    # Replacing the key is how the owner revokes a leaked one, so it is ALWAYS
    # allowed — refusing it would leave a leaked key working. What is limited is
    # the other effect: a new key generation, which gives a fresh new-
    # installation allowance (see validate). Unlimited fresh allowances would
    # allow seat cycling, so past MAX_ROTATIONS per period the key still changes
    # but the generation, and its allowance, stays.
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=ENTITLEMENT_SECONDS)
    recent = [t for t in org.get("licence_rotations", [])
              if (t if t.tzinfo else t.replace(tzinfo=timezone.utc)) >= window_start]
    fresh_allowance = len(recent) < MAX_ROTATIONS

    key = _new_key()
    update = {"$set": {"licence_key": key,
                       "licence_rotations": recent + [now] if fresh_allowance else recent}}
    if fresh_allowance:
        update["$inc"] = {"licence_key_gen": 1}
    # Compare-and-swap on the old key: of two replacements racing, only one
    # applies, so both cannot pass the check above on the same stale count.
    res = await db.organizations.update_one(
        {"org_id": admin.org_id, "licence_key": org.get("licence_key")}, update)
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail="The licence key was just replaced — reload the page")

    # Every installation must be given the new key, so the old ones (including
    # any a leaked key had taken) are marked removed — marked, not deleted, so
    # the record stays. One the owner pastes the new key into rejoins its place.
    await db.licence_activations.update_many(
        {"org_id": admin.org_id, "removed": {"$ne": True}},
        {"$set": {"removed": True, "removed_by": "rotation", "removed_at": now}})
    entitled = org.get("subscription_status") in ENTITLED_STATUSES
    return LicenceKeyPublic(
        licence_key=key,
        plan=org.get("plan", "trial"),
        max_cameras=None if entitled else FREE_TIER_MAX_CAMERAS,
    )
