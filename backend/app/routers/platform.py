import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import settings
from app.database import get_db
from app.models import (
    LoginRequest, PlanUpdate, ComplaintUpdate, TenantPlanUpdate,
    effective_site_status, SITE_OFFLINE_AFTER_SECONDS,
)
from app.security import (
    verify_password, create_platform_token, require_platform_admin,
    PLATFORM_COOKIE_NAME,
)
from app.rate_limit import rate_limiter
from app.runtime import uptime_seconds
from app.routers.ws import subscriber_stats
from app.plans import list_plans, seed_plans, EDITABLE_FIELDS
from fastapi import HTTPException


async def _agent_pipeline_health(db) -> dict:
    """Per-camera pipeline health aggregated from edge-agent heartbeats
    (detection runs at the edge now, not in the cloud). Keyed by camera_id."""
    out = {}
    async for site in db.sites.find({}, {"org_id": 1, "status": 1, "last_seen_at": 1, "pipeline_health": 1}):
        # Derived, not the stored flag — a dead agent's last reported pipeline
        # health would otherwise be presented as current.
        site_online = effective_site_status(site) == "online"
        for p in site.get("pipeline_health", []) or []:
            out[p["camera_id"]] = {
                "org_id": site["org_id"],
                "fps": p.get("fps", 0),
                "inference_ms": p.get("inference_ms", 0),
                "last_frame_age_s": p.get("last_frame_age_s"),
                "online": bool(p.get("online")) and site_online,
            }
    return out

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

    since = datetime.utcnow() - timedelta(hours=24)
    health = await _agent_pipeline_health(db)
    online_pipelines = sum(1 for h in health.values() if h["online"])

    orgs = await db.organizations.count_documents({})
    users = await db.users.count_documents({})
    cameras = await db.cameras.count_documents({})
    alerts_24h = await db.alerts.count_documents({"timestamp": {"$gte": since}})
    unconfirmed = await db.alerts.count_documents({"promoted_to_incident": {"$ne": True}})
    sites_total = await db.sites.count_documents({})
    # Counted by recent heartbeat, not the stored flag, which is never cleared.
    sites_online = await db.sites.count_documents({
        "last_seen_at": {"$gte": datetime.utcnow() - timedelta(seconds=SITE_OFFLINE_AFTER_SECONDS)}
    })

    status = "operational" if db_connected else "degraded"

    return {
        "status": status,
        "uptime_seconds": uptime_seconds(),
        "fleet": {
            "companies": orgs,
            "users": users,
            "cameras": cameras,
            "active_pipelines": online_pipelines,
        },
        "sites": {"total": sites_total, "online": sites_online},
        "alerts": {"last_24h": alerts_24h, "unconfirmed": unconfirmed},
        "detector": {
            # Detection runs on the edge agents now, not in the cloud.
            "runs_at": "edge",
            "model_path": settings.MODEL_PATH,
            "process_fps_target": settings.PROCESS_FPS,
        },
        "infra": {
            "database_connected": db_connected,
            "database_ping_ms": ping_ms,
            "redis_configured": bool(settings.REDIS_URL),
            "websocket_viewers": subscriber_stats()["total_connections"],
        },
    }


@router.get("/tenants")
async def platform_tenants(_admin: dict = Depends(require_platform_admin)):
    db = get_db()
    health = await _agent_pipeline_health(db)   # camera_id -> {org_id, fps, online, ...}
    since = datetime.utcnow() - timedelta(hours=24)

    tenants = []
    async for org in db.organizations.find({}).sort("created_at", 1):
        org_id = org["org_id"]
        cameras = await db.cameras.find({"org_id": org_id}).to_list(500)
        enabled = [c for c in cameras if c.get("enabled", True)]

        online = 0
        for c in enabled:
            h = health.get(c["camera_id"])
            if h and h["online"]:
                online += 1

        # Degraded = a camera the customer expects to be running isn't reporting.
        degraded = online < len(enabled)

        users = await db.users.count_documents({"org_id": org_id})
        alerts_24h = await db.alerts.count_documents({"org_id": org_id, "timestamp": {"$gte": since}})

        tenants.append({
            "org_id": org_id,
            "name": org["name"],
            "plan": org.get("plan", "trial"),
            "subscription_status": org.get("subscription_status", "trialing"),
            "users": users,
            "cameras_total": len(cameras),
            "cameras_online": online,
            "cameras_expected": len(enabled),
            "alerts_24h": alerts_24h,
            "degraded": degraded,
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
    cameras = await db.cameras.count_documents({"org_id": org_id})
    users = await db.users.count_documents({"org_id": org_id})
    limits = plans[body.plan]
    warnings = []
    if cameras > limits["max_cameras"]:
        warnings.append(
            f"{cameras} cameras exceeds the {limits['label']} limit of {limits['max_cameras']} — "
            "existing cameras keep running, but no new ones can be added."
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


# ── Pipelines & models ──────────────────────────────────────────────────────

@router.get("/pipelines")
async def platform_pipelines(_admin: dict = Depends(require_platform_admin)):
    db = get_db()
    health = await _agent_pipeline_health(db)   # from edge-agent heartbeats

    # Join reported pipeline health with camera + org metadata.
    org_names = {o["org_id"]: o["name"] async for o in db.organizations.find({}, {"org_id": 1, "name": 1})}
    rows = []
    for camera_id, h in health.items():
        cam = await db.cameras.find_one({"camera_id": camera_id}, {"name": 1, "zone": 1, "org_id": 1})
        rows.append({
            "camera_id": camera_id,
            "camera_name": cam["name"] if cam else "(unknown)",
            "zone": cam.get("zone") if cam else None,
            "org_name": org_names.get(h["org_id"], "(unknown)"),
            "fps": h["fps"],
            "inference_ms": h["inference_ms"],
            "last_frame_age_s": h["last_frame_age_s"],
            "online": h["online"],
        })
    rows.sort(key=lambda r: (r["online"], r["org_name"]))

    return {
        "model": {
            # Detection runs on the edge agents; the cloud no longer loads a model.
            "runs_at": "edge",
            "model_path": settings.MODEL_PATH,
            "default_confidence_threshold": settings.CONFIDENCE_THRESHOLD,
            "process_fps_target": settings.PROCESS_FPS,
        },
        "pipelines": rows,
        "total": len(rows),
        "online": sum(1 for r in rows if r["online"]),
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
