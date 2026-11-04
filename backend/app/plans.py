"""DB-backed plan catalog.

FiremeX is sold by the camera, because a camera is what the customer gets value
from: each one is a room that is watched for fire. Home Assistant installations
are not a selling unit — one subscription licenses one installation, and the
camera count travels inside the signed licence that installation receives.

    free     1 camera, forever. Where a trial or a lapsed subscription lands.
    trial    14 days, 4 cameras, no card. Not purchasable.
    starter  "Home": a flat bundle of 4 cameras.
    pro      "Pro": priced per camera, 5 to 64, with a bigger team.

Every paid plan has a monthly and a yearly price; a year costs ten months.

Plans live in a `plans` collection so FiremeX staff can edit labels, prices,
team sizes and features from the platform console. Defaults below seed the
collection; get_plan() falls back to them when the DB has no row (e.g. in tests,
which do not run the startup seed).
"""
from app.database import get_db

# Bumped when the catalog's SHAPE changes. Rows written under an older version
# describe plans that no longer exist (the 2026 install-based plans) and are
# replaced, not merged — merging would keep a price for a unit we no longer sell.
CATALOG_VERSION = 2

TRIAL_DAYS = 14

DEFAULT_PLANS = {
    "free": {
        "plan_id": "free", "label": "Free", "order": 0, "purchasable": False,
        "price_month_usd": 0, "price_year_usd": 0, "per_camera": False,
        "cameras": 1, "min_cameras": 1, "max_cameras": 1,
        "max_users": 1, "max_installs": 1,
        "features": ["1 camera, free for good", "Fire, smoke and small-flame detection",
                     "Runs fully local, works offline"],
    },
    "trial": {
        "plan_id": "trial", "label": "Free trial", "order": 1, "purchasable": False,
        "price_month_usd": 0, "price_year_usd": 0, "per_camera": False,
        "cameras": 4, "min_cameras": 4, "max_cameras": 4,
        "max_users": 3, "max_installs": 1,
        "features": [f"{TRIAL_DAYS} days, no card needed", "Up to 4 cameras",
                     "Everything in Home"],
    },
    "starter": {
        "plan_id": "starter", "label": "Home", "order": 2, "purchasable": True,
        "price_month_usd": 9, "price_year_usd": 90, "per_camera": False,
        "cameras": 4, "min_cameras": 4, "max_cameras": 4,
        "max_users": 3, "max_installs": 1,
        "features": ["Up to 4 cameras", "Phone alerts through Home Assistant",
                     "Detection history with photos", "Email support"],
    },
    "pro": {
        "plan_id": "pro", "label": "Pro", "order": 3, "purchasable": True,
        "price_month_usd": 3, "price_year_usd": 30, "per_camera": True,
        "cameras": 5, "min_cameras": 5, "max_cameras": 64,
        "max_users": 25, "max_installs": 1,
        "features": ["5 to 64 cameras, pay for what you use", "Everything in Home",
                     "Up to 25 team members", "Priority support"],
    },
}

INTERVALS = ("month", "year")

EDITABLE_FIELDS = {"label", "price_month_usd", "price_year_usd", "max_users", "features"}


def _with_legacy_fields(plan: dict) -> dict:
    """Older code paths (the retired cloud-camera routes, the staff console's
    revenue estimate) read `price_usd` and `max_cameras`. Kept derived, never
    stored separately, so the two cannot drift apart."""
    return {**plan, "price_usd": plan.get("price_month_usd", 0)}


async def seed_plans():
    """Insert missing default plans and replace rows from an older catalog.
    Never overwrites staff edits made under the current catalog."""
    db = get_db()
    for plan_id, doc in DEFAULT_PLANS.items():
        row = {**doc, "catalog_version": CATALOG_VERSION}
        await db.plans.update_one(
            {"plan_id": plan_id, "catalog_version": {"$ne": CATALOG_VERSION}},
            {"$set": row}, upsert=False)
        await db.plans.update_one({"plan_id": plan_id}, {"$setOnInsert": row}, upsert=True)


async def list_plans() -> list[dict]:
    db = get_db()
    plans = await db.plans.find({"catalog_version": CATALOG_VERSION}, {"_id": 0}).sort("order", 1).to_list(50)
    if len(plans) < len(DEFAULT_PLANS):
        # First read, or rows from an older catalog: seed, then re-query.
        await seed_plans()
        plans = await db.plans.find({"catalog_version": CATALOG_VERSION}, {"_id": 0}).sort("order", 1).to_list(50)
    return [_with_legacy_fields(p) for p in plans]


async def get_plan(plan_id: str) -> dict:
    db = get_db()
    plan = await db.plans.find_one({"plan_id": plan_id, "catalog_version": CATALOG_VERSION}, {"_id": 0})
    return _with_legacy_fields(plan or DEFAULT_PLANS.get(plan_id, DEFAULT_PLANS["free"]))


def price_cents(plan: dict, interval: str) -> int:
    return int(round(plan[f"price_{interval}_usd"] * 100))


def clamp_cameras(plan: dict, cameras) -> int:
    """The number of cameras a subscription to `plan` covers. Flat plans ignore
    the request; per-camera plans keep it inside the plan's range."""
    if not plan.get("per_camera"):
        return plan["cameras"]
    try:
        n = int(cameras)
    except (TypeError, ValueError):
        n = plan["min_cameras"]
    return max(plan["min_cameras"], min(plan["max_cameras"], n))


async def get_plan_limits(plan_id: str) -> dict:
    """{max_cameras, max_users, label} for a plan — DB first, defaults as fallback."""
    plan = await get_plan(plan_id)
    return {"max_cameras": plan["max_cameras"], "max_users": plan["max_users"], "label": plan["label"]}
