import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import settings
from app.database import get_db
from app.models import (
    LoginRequest, PlanUpdate, ComplaintUpdate, TenantPlanUpdate, PLAN_LIMITS,
)
from app.security import (
    verify_password, create_platform_token, require_platform_admin,
    PLATFORM_COOKIE_NAME,
)
from app.rate_limit import rate_limiter
from app.runtime import uptime_seconds
from app.plans import list_plans, seed_plans, EDITABLE_FIELDS
from fastapi import HTTPException


# FiremeX runs as the Home Assistant add-on. The cloud never sees cameras or
# detections; what it does see is each add-on checking its access token, so
# installations and their last check-in are the fleet the staff look after.
# An add-on checks once a day while running — quieter than this means it has
# stopped, lost internet, or lost its token.
QUIET_AFTER = timedelta(hours=26)


def _utc(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _live_installs(db, query=None) -> list[dict]:
    return await db.licence_activations.find(
        {"removed": {"$ne": True}, **(query or {})}).to_list(5000)

# NOTE: this whole router is the vendor/ops console. It is cross-tenant by
# design and must only ever be reachable by a platform super-admin — never a
# customer. Every route below (except login) depends on require_platform_admin.
router = APIRouter(prefix="/platform", tags=["platform"])

PLATFORM_LOGIN_LIMIT = Depends(rate_limiter(max_attempts=8, window_seconds=60))


def _set_platform_cookie(response: Response, admin_id: str):
    response.set_cookie(
        key=PLATFORM_COOKIE_NAME,
        value=create_platform_token(admin_id),
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )


@router.post("/auth/login", dependencies=[PLATFORM_LOGIN_LIMIT])
async def platform_login(body: LoginRequest, response: Response):
    db = get_db()
    email = body.email.strip().lower()
    admin = await db.platform_admins.find_one({"email": email})
    if not admin or not verify_password(body.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    _set_platform_cookie(response, admin["admin_id"])
    return {"email": admin["email"], "name": admin["name"]}


@router.post("/auth/logout")
async def platform_logout(response: Response):
    response.delete_cookie(PLATFORM_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/auth/me")
async def platform_me(admin: dict = Depends(require_platform_admin)):
    return {"email": admin["email"], "name": admin["name"]}


@router.get("/overview")
async def platform_overview(_admin: dict = Depends(require_platform_admin)):
    db = get_db()

    # DB connectivity + ping latency
    ping_ms, db_connected = None, True
    try:
        t0 = time.time()
        await db.command("ping")
        ping_ms = round((time.time() - t0) * 1000, 1)
    except Exception:
        db_connected = False

    installs = await _live_installs(db)
    now = datetime.now(timezone.utc)
    checked_in = sum(1 for i in installs if _utc(i["last_seen"]) >= now - QUIET_AFTER)

    orgs = await db.organizations.count_documents({})
    users = await db.users.count_documents({})
    status = "operational" if db_connected else "degraded"

    return {
        "status": status,
        "uptime_seconds": uptime_seconds(),
        "fleet": {
            "companies": orgs,
            "users": users,
            "installations": len(installs),
            "installations_checked_in": checked_in,
        },
        # Which add-on versions are out there — tells staff who still needs to
        # press Update before a fix reaches them.
        "addon_versions": dict(Counter(i.get("addon_version") or "unknown" for i in installs)
                               .most_common()),
        "infra": {
            "database_connected": db_connected,
            "database_ping_ms": ping_ms,
            "redis_configured": bool(settings.REDIS_URL),
        },
    }


@router.get("/tenants")
async def platform_tenants(_admin: dict = Depends(require_platform_admin)):
    db = get_db()
    now = datetime.now(timezone.utc)

    tenants = []
    async for org in db.organizations.find({}).sort("created_at", 1):
        org_id = org["org_id"]
        installs = await _live_installs(db, {"org_id": org_id})
        last = max((_utc(i["last_seen"]) for i in installs), default=None)
        # Needs attention = it was set up, but no installation has checked in
        # lately. A customer who never installed is not "degraded".
        quiet = bool(installs) and last < now - QUIET_AFTER

        tenants.append({
            "org_id": org_id,
            "name": org["name"],
            "plan": org.get("plan", "trial"),
            "subscription_status": org.get("subscription_status", "trialing"),
            "users": await db.users.count_documents({"org_id": org_id}),
            "installations": len(installs),
            "max_installations": PLAN_LIMITS.get(org.get("plan", "trial"), {}).get("max_installs", 1),
            "last_check_in": last.isoformat() if last else None,
            "setup_completed": bool(org.get("onboarding_completed")),
            "degraded": quiet,
        })

    return {"tenants": tenants, "degraded_count": sum(1 for t in tenants if t["degraded"])}


VALID_SUBSCRIPTION_STATUSES = {"trialing", "active", "past_due", "canceled", "incomplete"}


@router.patch("/tenants/{org_id}/plan")
async def platform_set_tenant_plan(
    org_id: str,
    body: TenantPlanUpdate,
    admin: dict = Depends(require_platform_admin),
):
    """Move a tenant onto a different plan by hand.

    Payment collection isn't wired up yet, so this is currently the ONLY way a
    customer can get off the trial. It writes the same two fields a Stripe
    webhook would (plan, subscription_status) plus an audit trail marking the
    change as manual, so the two sources of truth stay distinguishable.

    Downgrades are allowed even when the tenant is already over the new plan's
    ceiling: plan limits are enforced when creating cameras/users, not
    retroactively, and silently deleting a customer's cameras to satisfy a
    billing change would be far worse than letting them sit over quota. The
    response reports any breach so the console can surface it.
    """
    db = get_db()

    plans = {p["plan_id"]: p for p in await list_plans()}
    if body.plan not in plans:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plan '{body.plan}' — valid plans: {sorted(plans)}",
        )

    status = body.subscription_status
    if status is None:
        status = "trialing" if plans[body.plan].get("price_usd", 0) == 0 else "active"
    if status not in VALID_SUBSCRIPTION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subscription status — valid: {sorted(VALID_SUBSCRIPTION_STATUSES)}",
        )

    org = await db.organizations.find_one({"org_id": org_id})
    if not org:
        raise HTTPException(status_code=404, detail="Tenant not found")

    updates = {
        "plan": body.plan,
        "subscription_status": status,
        # Audit trail. Kept deliberately explicit so a future Stripe webhook can
        # tell "a human set this" apart from "the payment provider set this".
        "plan_source": "manual",
        "plan_updated_by": admin.get("email"),
        "plan_updated_at": datetime.utcnow(),
        "plan_update_note": body.note or "",
    }
    await db.organizations.update_one({"org_id": org_id}, {"$set": updates})

    # Report (don't enforce) an over-quota downgrade.
    installs = len(await _live_installs(db, {"org_id": org_id}))
    users = await db.users.count_documents({"org_id": org_id})
    limits = plans[body.plan]
    max_installs = PLAN_LIMITS.get(body.plan, {}).get("max_installs", 1)
    warnings = []
    if installs > max_installs:
        warnings.append(
            f"{installs} Home Assistant installations exceeds the {limits['label']} limit of "
            f"{max_installs} — the newest ones drop to the one-camera free tier at their next check."
        )
    if users > limits["max_users"]:
        warnings.append(
            f"{users} users exceeds the {limits['label']} limit of {limits['max_users']} — "
            "existing users keep access, but no new ones can be invited."
        )

    return {
        "org_id": org_id,
        "name": org["name"],
        "plan": body.plan,
        "subscription_status": status,
        "plan_source": "manual",
        "changed_by": admin.get("email"),
        "warnings": warnings,
    }


# ── Plans (view + edit prices/limits/features) ──────────────────────────────

@router.get("/plans")
async def platform_plans(_admin: dict = Depends(require_platform_admin)):
    return {"plans": await list_plans()}


@router.patch("/plans/{plan_id}")
async def platform_update_plan(plan_id: str, body: PlanUpdate, _admin: dict = Depends(require_platform_admin)):
    db = get_db()
    await seed_plans()   # ensure the catalog rows exist before editing
    updates = {k: v for k, v in body.model_dump().items() if v is not None and k in EDITABLE_FIELDS}
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields provided")
    result = await db.plans.find_one_and_update(
        {"plan_id": plan_id}, {"$set": updates}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result


# ── Billing / revenue ───────────────────────────────────────────────────────

@router.get("/billing")
async def platform_billing(_admin: dict = Depends(require_platform_admin)):
    db = get_db()
    plans = {p["plan_id"]: p for p in await list_plans()}

    rows, mrr = [], 0
    counts = {"active": 0, "trialing": 0, "past_due": 0, "canceled": 0, "other": 0}
    async for org in db.organizations.find({}).sort("created_at", 1):
        status = org.get("subscription_status", "trialing")
        plan_id = org.get("plan", "trial")
        price = plans.get(plan_id, {}).get("price_usd", 0)
        paying = status == "active" and price > 0
        if paying:
            mrr += price
        counts[status if status in counts else "other"] += 1
        rows.append({
            "org_id": org["org_id"],
            "name": org["name"],
            "plan": plan_id,
            "subscription_status": status,
            "price_usd": price,
            "paying": paying,
            "has_payment_method": bool(org.get("stripe_customer_id")),
            "current_period_end": org.get("current_period_end").isoformat() if org.get("current_period_end") else None,
            "trial_ends_at": org.get("trial_ends_at").isoformat() if org.get("trial_ends_at") else None,
        })

    return {
        "mrr_usd": mrr,
        "arr_usd": mrr * 12,
        "paying_customers": sum(1 for r in rows if r["paying"]),
        "status_counts": counts,
        "customers": rows,
    }


# ── Home Assistant installations ────────────────────────────────────────────

@router.get("/installations")
async def platform_installations(_admin: dict = Depends(require_platform_admin)):
    """Every add-on using a customer's token, quietest first — the ones that
    stopped checking in are the ones worth a call."""
    db = get_db()
    now = datetime.now(timezone.utc)
    org_names = {o["org_id"]: o["name"] async for o in db.organizations.find({}, {"org_id": 1, "name": 1})}
    rows = []
    for i in await _live_installs(db):
        last = _utc(i["last_seen"])
        rows.append({
            "install_id": i["install_id"],
            "org_name": org_names.get(i["org_id"], "(unknown)"),
            "addon_version": i.get("addon_version"),
            "first_seen": _utc(i["first_seen"]).isoformat(),
            "last_seen": last.isoformat(),
            "checked_in": last >= now - QUIET_AFTER,
        })
    rows.sort(key=lambda r: (r["checked_in"], r["last_seen"]))
    return {
        "installations": rows,
        "total": len(rows),
        "checked_in": sum(1 for r in rows if r["checked_in"]),
    }


# ── Complaints (cross-tenant support queue) ─────────────────────────────────

@router.get("/complaints")
async def platform_complaints(_admin: dict = Depends(require_platform_admin)):
    db = get_db()
    items = await db.complaints.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    open_count = sum(1 for c in items if c["status"] != "resolved")
    return {"complaints": items, "open_count": open_count}


@router.patch("/complaints/{complaint_id}")
async def platform_update_complaint(complaint_id: str, body: ComplaintUpdate, _admin: dict = Depends(require_platform_admin)):
    from datetime import datetime
    db = get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates.get("status") and updates["status"] not in ("open", "in_progress", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status")
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = datetime.utcnow()
    result = await db.complaints.find_one_and_update(
        {"complaint_id": complaint_id}, {"$set": updates}, return_document=True, projection={"_id": 0}
    )
    if not result:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return result
