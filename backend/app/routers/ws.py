import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models import Alert
from app.database import get_db
from app.security import COOKIE_NAME, decode_session_token
from app.services.notifications import send_alert_email
from app.relay import relay_hub

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{camera_id}")
async def camera_ws(websocket: WebSocket, camera_id: str):
    """Browser viewer for a camera's live feed. Frames are relayed from the
    site's edge agent (see relay_hub) — the cloud holds no video itself."""
    token = websocket.cookies.get(COOKIE_NAME)
    claims = decode_session_token(token) if token else None
    user_id = claims.get("sub") if claims else None
    if not user_id:
        await websocket.close(code=4401)
        return

    db = get_db()
    user = await db.users.find_one({"user_id": user_id})
    camera = await db.cameras.find_one({"camera_id": camera_id})
    if not user or not camera or camera["org_id"] != user["org_id"]:
        await websocket.close(code=4403)
        return
    if claims.get("ver", 0) != user.get("token_version", 0):
        await websocket.close(code=4401)
        return

    org_id = user["org_id"]
    await websocket.accept()
    await relay_hub.add_viewer(camera_id, org_id, websocket)
    logger.info(f"viewer connected: {camera_id}")
    try:
        while True:
            await websocket.receive_text()   # keepalive / client pings
    except WebSocketDisconnect:
        pass
    finally:
        await relay_hub.remove_viewer(camera_id, org_id, websocket)
        logger.info(f"viewer disconnected: {camera_id}")


def subscriber_stats() -> dict:
    """Live viewer counts, for the platform health console."""
    return relay_hub.stats()


async def save_alert(alert: Alert):
    """Persist a raw detection. (Retained for compatibility; edge events now
    flow through /agent/events.)"""
    db = get_db()
    await db.alerts.insert_one(alert.model_dump())
    logger.warning(f"ALERT: {alert.hazard_type} on {alert.camera_name} ({alert.confidence:.0%})")
    await send_alert_email(alert)
