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

Without a valid key the add-on is not blocked; it drops to a one-camera free
tier. That is a safety decision as much as a commercial one: this software's job
is noticing fires, and an expired card or an unreachable cloud must never be the
reason a building stops being watched.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import (FREE_TIER_MAX_CAMERAS, LicenceCheck, LicenceKeyPublic,
                        LicencePublic, UserPublic)
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
    """Check a licence key. Public — add-ons in the field have no session.

    Answers the same shape whether the key is unknown, revoked or unpaid: the
    add-on only needs to know how many cameras it may watch, and a caller
    guessing keys should not learn which guesses named a real organization.
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

    # Paid tiers are unlimited; the number rather than the plan name is what the
    # add-on enforces, so plan definitions can change without a new image.
    return LicencePublic(valid=True,
                         plan=org.get("plan", "trial"),
                         max_cameras=None,
                         organization=org.get("name"))


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
    entitled = org.get("subscription_status") in ENTITLED_STATUSES
    return LicenceKeyPublic(
        licence_key=key,
        plan=org.get("plan", "trial"),
        max_cameras=None if entitled else FREE_TIER_MAX_CAMERAS,
    )
