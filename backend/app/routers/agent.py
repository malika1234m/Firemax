"""Edge-agent gateway.

The agent runs on the customer's own network, always dials OUT to these
endpoints (so no inbound ports are opened on the customer firewall), pulls its
config, runs detection locally, and reports events + health up. Every route is
authenticated by the site's agent token (require_agent), never a user session.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.database import get_db
from app.models import AgentHeartbeat, AgentEvent, Alert
from app.security import require_agent, hash_agent_token
from app.crypto import decrypt_secret
from app.services.notifications import send_alert_email
from app.relay import relay_hub

logger = logging.getLogger("agent")
router = APIRouter(prefix="/agent", tags=["agent"])

# `agent.py --selftest` deliberately posts one event for a camera that does not
# exist, to prove the whole path end to end before any camera is configured.
# It must survive the deleted-camera check below or commissioning breaks.
SELFTEST_CAMERA_ID = "selftest"


@router.get("/config")
async def agent_config(site: dict = Depends(require_agent)):
    """Everything the agent needs to run: which cameras to watch, detection
    tuning, and the local Home Assistant connection (decrypted here so the HA
    token ends up only on the customer's own box)."""
    db = get_db()
    org_id = site["org_id"]
    org = await db.organizations.find_one({"org_id": org_id})
    cameras = await db.cameras.find({"org_id": org_id, "enabled": True}).to_list(200)

    ha_token = None
    if org and org.get("ha_token_encrypted"):
        ha_token = decrypt_secret(org["ha_token_encrypted"])

    return {
        "site_id": site["site_id"],
        "cameras": [
            {"camera_id": c["camera_id"], "name": c["name"], "stream_url": c["stream_url"], "zone": c.get("zone", "Unassigned")}
            for c in cameras
        ],
        "detection": {
            "confidence_threshold": org.get("confidence_threshold", 0.5) if org else 0.5,
            "alert_cooldown_seconds": org.get("alert_cooldown_seconds", 30) if org else 30,
        },
        "home_assistant": {"url": org.get("ha_url") or None, "token": ha_token} if org else {"url": None, "token": None},
    }


@router.post("/heartbeat")
async def agent_heartbeat(body: AgentHeartbeat, site: dict = Depends(require_agent)):
    """Liveness + per-camera pipeline health. Marks the site online and stores
    the latest pipeline stats for the platform console / dashboards."""
    db = get_db()
    await db.sites.update_one(
        {"site_id": site["site_id"]},
        {"$set": {
            "status": "online",
            "last_seen_at": datetime.utcnow(),
            "agent_version": body.agent_version,
            "pipeline_health": [p.model_dump() for p in body.pipelines],
        }},
    )
    return {"status": "ok"}


@router.websocket("/ws")
async def agent_ws(websocket: WebSocket):
    """Persistent outbound connection from a site's edge agent. Carries frames
    UP (for the live-feed relay) and stream start/stop commands DOWN. Authed by
    the site token in the handshake header."""
    raw = websocket.headers.get("x-agent-token")
    site = None
    if raw:
        site = await get_db().sites.find_one({"token_hash": hash_agent_token(raw)})
    if not site:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    relay_hub.add_agent(site["site_id"], site["org_id"], websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "frame" and msg.get("camera_id"):
                await relay_hub.on_agent_frame(msg["camera_id"], {
                    "frame_b64": msg.get("frame_b64"),
                    "detections": msg.get("detections", []),
                    "fps": msg.get("fps", 0),
                    "timestamp": msg.get("ts") or datetime.utcnow().isoformat(),
                })
    except WebSocketDisconnect:
        pass
    finally:
        relay_hub.remove_agent(site["site_id"])


@router.post("/events")
async def agent_events(events: list[AgentEvent], site: dict = Depends(require_agent)):
    """Detections from the edge become Alerts in the cloud (scoped to the
    site's org). Raw detections only — HA automations/authority calls still
    require a human to promote them to an incident."""
    db = get_db()
    created, ignored = 0, 0
    for e in events:
        # The agent reads its camera list once at startup, so after a camera is
        # deleted or disabled it keeps watching and reporting on it. Without
        # this check those events became alerts for a camera the operator can
        # no longer see anywhere — incidents appearing from nothing. The cloud
        # is the authority on which cameras exist, so it rejects the rest.
        if e.camera_id != SELFTEST_CAMERA_ID:
            camera = await db.cameras.find_one(
                {"camera_id": e.camera_id, "org_id": site["org_id"]},
                {"enabled": 1},
            )
            if not camera or not camera.get("enabled", True):
                ignored += 1
                continue

        alert = Alert(
            org_id=site["org_id"],
            camera_id=e.camera_id,
            camera_name=e.camera_name,
            hazard_type=e.hazard_type,
            confidence=e.confidence,
            zone=e.zone,
            frame_b64=e.frame_b64,
        )
        await db.alerts.insert_one(alert.model_dump())
        await send_alert_email(alert)
        created += 1

    if ignored:
        logger.info(
            f"[{site['site_id']}] ignored {ignored} event(s) for cameras that are "
            "deleted or disabled — the agent needs a restart to pick up the change"
        )
    return {"status": "ok", "created": created, "ignored": ignored}
