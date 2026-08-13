"""Per-camera liveness, derived from edge-agent heartbeats.

Detection runs at the edge, so the cloud only knows a camera is alive because
an agent said so recently. Every surface that shows camera status must read it
from here rather than from `camera.enabled`, which merely records whether an
operator has switched the camera on — a camera can be enabled for months with
no agent running anywhere.

Getting that backwards is the dangerous direction for a fire-safety product:
"All cameras reporting" on a dashboard where nothing is running is worse than
showing nothing at all.
"""
from app.models import effective_site_status


async def camera_health(db, org_id: str | None = None) -> dict:
    """camera_id -> {org_id, fps, inference_ms, last_frame_age_s, online}.

    A camera is online only when its own pipeline reported healthy AND the site
    reporting it is itself still heartbeating — a dead agent's final heartbeat
    must not keep its cameras looking alive forever.
    """
    query = {"org_id": org_id} if org_id else {}
    out: dict[str, dict] = {}
    async for site in db.sites.find(
        query, {"org_id": 1, "status": 1, "last_seen_at": 1, "pipeline_health": 1}
    ):
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
