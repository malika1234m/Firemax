"""DB-backed plan catalog.

Plan prices, limits, and feature lists used to live hardcoded in the backend
and frontend. They now live in a `plans` collection so the FiremeX staff can
edit them from the platform console. Defaults below seed the collection on
first run; get_plan_limits() falls back to them if the DB has no row yet (e.g.
in tests, which don't run the startup seed).
"""
from app.database import get_db
from app.models import PLAN_LIMITS

# plan_id -> full catalog entry. Trial is free and not purchasable.
DEFAULT_PLANS = {
    "trial": {
        "plan_id": "trial", "label": "Trial", "price_usd": 0, "order": 0,
        "max_cameras": PLAN_LIMITS["trial"]["max_cameras"],
        "max_users": PLAN_LIMITS["trial"]["max_users"],
        "features": ["Full detection pipeline", "Live feed & incident review", "Email alerts"],
        "stripe_lookup_key": None,
    },
    "starter": {
        "plan_id": "starter", "label": "Starter", "price_usd": 49, "order": 1,
        "max_cameras": PLAN_LIMITS["starter"]["max_cameras"],
        "max_users": PLAN_LIMITS["starter"]["max_users"],
        "features": ["Everything in Trial", "SMS + call to authorities", "Shift scheduling"],
        "stripe_lookup_key": "firemex_starter_monthly",
    },
    "pro": {
        "plan_id": "pro", "label": "Pro", "price_usd": 199, "order": 2,
        "max_cameras": PLAN_LIMITS["pro"]["max_cameras"],
        "max_users": PLAN_LIMITS["pro"]["max_users"],
        "features": ["Everything in Starter", "Priority detection processing", "Dedicated support"],
        "stripe_lookup_key": "firemex_pro_monthly",
    },
}

EDITABLE_FIELDS = {"label", "price_usd", "max_cameras", "max_users", "features"}


async def seed_plans():
    """Idempotently insert any missing default plans. Never overwrites edits."""
    db = get_db()
    for plan_id, doc in DEFAULT_PLANS.items():
        await db.plans.update_one({"plan_id": plan_id}, {"$setOnInsert": doc}, upsert=True)


async def list_plans() -> list[dict]:
    db = get_db()
    plans = await db.plans.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    if not plans:
        # Seed on first read so the catalog exists even if the startup seed
        # didn't run (e.g. in tests), then re-query.
        await seed_plans()
        plans = await db.plans.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    return plans


async def get_plan(plan_id: str) -> dict:
    db = get_db()
    plan = await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})
    return plan or DEFAULT_PLANS.get(plan_id, DEFAULT_PLANS["trial"])


async def get_plan_limits(plan_id: str) -> dict:
    """{max_cameras, max_users, label} for a plan — DB first, defaults as fallback."""
    plan = await get_plan(plan_id)
    return {"max_cameras": plan["max_cameras"], "max_users": plan["max_users"], "label": plan["label"]}
