"""What an organization is entitled to right now.

Everything that grants cameras — the add-on's licence check, the billing page,
the access-token page — asks this module, so the rules live in one place:

    trialing, trial not over        trial cameras (4)
    trialing, trial over            -> moved to the free plan, 1 camera
    active                          the subscription's cameras
    past_due, within grace          the subscription's cameras, with a warning
    past_due, grace over            1 camera until the payment goes through
    canceled / incomplete / ended   1 camera

The free tier is the floor, never zero: this software watches for fires, and an
expired trial or a declined card must not be why a building stops being watched.

Trial expiry is applied lazily, the first time anything looks at the org after
the trial ends, so no scheduler has to be running for a trial to end on time.
The change is a compare-and-set, so two requests racing record it once.
"""
from datetime import datetime, timedelta, timezone

from app import account_events
from app.plans import TRIAL_DAYS, get_plan

FREE_CAMERAS = 1

# How long a customer whose card was declined keeps their paid cameras while
# Stripe retries the payment. Stripe's Smart Retries run over about a week.
PAST_DUE_GRACE_DAYS = 7

PAID_STATUSES = {"active"}


def _utc(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def trial_end(org: dict):
    """When this org's trial ends. Organizations created before trials were
    dated get the standard length from their creation date."""
    end = _utc(org.get("trial_ends_at"))
    if end is None and org.get("created_at"):
        end = _utc(org["created_at"]) + timedelta(days=TRIAL_DAYS)
    return end


async def refresh(db, org: dict) -> dict:
    """Apply time-based changes (trial ended, payment grace over) and return the
    up-to-date org. Safe to call on every read."""
    if not org:
        return org
    now = datetime.now(timezone.utc)
    if org.get("subscription_status") == "trialing" and org.get("plan_source") != "manual":
        end = trial_end(org)
        if end and end <= now:
            res = await db.organizations.update_one(
                {"org_id": org["org_id"], "subscription_status": "trialing"},
                {"$set": {"plan": "free", "subscription_status": "trial_ended",
                          "trial_ended_at": now.replace(tzinfo=None)}})
            if res.modified_count:
                await account_events.record(
                    db, org["org_id"], "subscription_changed",
                    "Your free trial ended. FiremeX now watches 1 camera until you choose a plan.")
            org = await db.organizations.find_one({"org_id": org["org_id"]})
    return org


def state(org: dict) -> str:
    """trial | active | grace | free — after refresh()."""
    status = org.get("subscription_status")
    if status == "trialing":
        return "trial"
    if status in PAID_STATUSES:
        return "active"
    if status == "past_due":
        grace = _utc(org.get("grace_until"))
        if grace and grace > datetime.now(timezone.utc):
            return "grace"
    return "free"


async def cameras_allowed(org: dict) -> int:
    """How many cameras this org's licence lets its Home Assistant watch."""
    st = state(org)
    if st == "free":
        return FREE_CAMERAS
    plan = await get_plan(org.get("plan", "free"))
    if st == "trial":
        return plan["cameras"] if org.get("plan") == "trial" else (await get_plan("trial"))["cameras"]
    # Per-camera plans carry the purchased quantity on the org; flat plans
    # (and staff-granted plans without a quantity) use the plan's bundle.
    if plan.get("per_camera") and org.get("cameras"):
        return int(org["cameras"])
    return plan["cameras"]


async def summary(db, org: dict) -> dict:
    """Plain facts for the website: plan, state, cameras, dates."""
    org = await refresh(db, org)
    plan = await get_plan(org.get("plan", "free"))
    st = state(org)
    end = trial_end(org) if st == "trial" else None
    now = datetime.now(timezone.utc)
    return {
        "plan": org.get("plan", "free"),
        "label": plan["label"],
        "state": st,
        "status": org.get("subscription_status"),
        "cameras": await cameras_allowed(org),
        "interval": org.get("billing_interval"),
        "trial_ends_at": end,
        "trial_days_left": max(0, -(-int((end - now).total_seconds()) // 86400)) if end else None,
        "trial_ended": org.get("subscription_status") == "trial_ended",
        "renews_at": _utc(org.get("current_period_end")),
        "cancel_at_period_end": bool(org.get("cancel_at_period_end")),
        "grace_until": _utc(org.get("grace_until")) if org.get("subscription_status") == "past_due" else None,
        "plan_source": org.get("plan_source"),
    }
