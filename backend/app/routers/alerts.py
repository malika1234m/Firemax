import logging
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from app.database import get_db
from app.models import Alert, AlertUpdate, UserPublic
from app.security import get_current_user, require_admin
from app.services.notifications import notify_home_assistant, notify_authorities

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])

VALID_VERDICTS = {"true_fire", "false_alarm"}


@router.get("/", response_model=list[Alert])
async def list_alerts(
    limit: int = Query(50, le=200),
    camera_id: str = Query(None),
    hazard_type: str = Query(None),
    status: str = Query(None),
    user: UserPublic = Depends(get_current_user),
):
    db = get_db()
    query = {"org_id": user.org_id}
    if camera_id:
        query["camera_id"] = camera_id
    if hazard_type:
        query["hazard_type"] = hazard_type
    if status:
        query["status"] = status

    alerts = await db.alerts.find(query).sort("timestamp", -1).limit(limit).to_list(limit)
    return [Alert(**a) for a in alerts]


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    await db.alerts.delete_one({"alert_id": alert_id, "org_id": admin.org_id})
    return {"status": "deleted"}


@router.patch("/{alert_id}", response_model=Alert)
async def update_alert(alert_id: str, body: AlertUpdate, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if updates.get("status") == "resolved":
        verdict = updates.get("resolution_verdict")
        remark = updates.get("resolution_remark", "").strip() if updates.get("resolution_remark") else ""
        if verdict not in VALID_VERDICTS or not remark:
            raise HTTPException(
                status_code=400,
                detail="Resolving an incident requires resolution_verdict ('true_fire' or 'false_alarm') and a resolution_remark",
            )
        updates["resolved_by"] = user.user_id
        updates["resolved_at"] = datetime.utcnow()

    result = await db.alerts.find_one_and_update(
        {"alert_id": alert_id, "org_id": user.org_id}, {"$set": updates}, return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return Alert(**result)


async def _fire_incident_automations(alert: Alert):
    """Runs after the HTTP response has already gone back to the operator —
    a slow/unreachable Twilio or Home Assistant should never make the
    "Make Incident" button hang."""
    try:
        await notify_home_assistant(alert)
    except Exception:
        logger.exception(f"[promote] HA notification failed for {alert.alert_id}")
    try:
        await notify_authorities(alert)
    except Exception:
        logger.exception(f"[promote] Authority notification failed for {alert.alert_id}")


@router.post("/{alert_id}/promote", response_model=Alert)
async def promote_to_incident(
    alert_id: str,
    background_tasks: BackgroundTasks,
    user: UserPublic = Depends(get_current_user),
):
    """Human confirmation step. Only after this fires do HA automations and
    authority calls/SMS go out — raw detections alone never trigger them."""
    db = get_db()
    existing = await db.alerts.find_one({"alert_id": alert_id, "org_id": user.org_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Alert not found")

    if existing.get("promoted_to_incident"):
        return Alert(**existing)

    updates = {
        "promoted_to_incident": True,
        "promoted_at": datetime.utcnow(),
        "promoted_by": user.user_id,
    }
    result = await db.alerts.find_one_and_update(
        {"alert_id": alert_id}, {"$set": updates}, return_document=True
    )
    alert = Alert(**result)

    background_tasks.add_task(_fire_incident_automations, alert)

    return alert


@router.get("/stats")
async def alert_stats(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    pipeline = [
        {"$match": {"org_id": user.org_id}},
        {"$group": {"_id": "$hazard_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    result = await db.alerts.aggregate(pipeline).to_list(20)
    total = await db.alerts.count_documents({"org_id": user.org_id})
    acknowledged = await db.alerts.count_documents({"org_id": user.org_id, "acknowledged": True})
    awaiting = await db.alerts.count_documents({"org_id": user.org_id, "acknowledged": {"$ne": True}})
    return {
        "total": total,
        "by_type": result,
        "sent": total,
        "acknowledged": acknowledged,
        "awaiting": awaiting,
        "failed": 0,
    }
