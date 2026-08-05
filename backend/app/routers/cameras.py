from fastapi import APIRouter, Depends, HTTPException
from app.models import Camera, CameraCreate, UserPublic
from app.plans import get_plan_limits
from app.database import get_db
from app.security import get_current_user, require_admin
from app.net_guard import assert_safe_target, UnsafeTargetError
import asyncio
import socket

# Cameras are configuration/registry only. Detection runs on each site's edge
# agent (see edge/), which pulls its camera list from GET /agent/config and
# reports events/health back — the cloud never opens a stream itself.

router = APIRouter(prefix="/cameras", tags=["cameras"])

DEFAULT_ZONES = ["Main Entrance", "Warehouse A", "Warehouse B", "Warehouse C", "Secure IT", "Exterior"]


@router.get("/", response_model=list[Camera])
async def list_cameras(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    cameras = await db.cameras.find({"org_id": user.org_id}).to_list(100)
    return [Camera(**c) for c in cameras]


@router.get("/zones")
async def list_zones(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    used = await db.cameras.distinct("zone", {"org_id": user.org_id})
    zones = sorted(set(DEFAULT_ZONES) | {z for z in used if z})
    return zones


@router.post("/", response_model=Camera)
async def add_camera(body: CameraCreate, admin: UserPublic = Depends(require_admin)):
    db = get_db()

    # Refuse stream URLs that would point the ingest pipeline at loopback /
    # link-local (cloud metadata) — see net_guard for the SSRF rationale.
    try:
        assert_safe_target(body.stream_url)
    except UnsafeTargetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    org = await db.organizations.find_one({"org_id": admin.org_id})
    limits = await get_plan_limits(org["plan"])
    camera_count = await db.cameras.count_documents({"org_id": admin.org_id})
    if camera_count >= limits["max_cameras"]:
        raise HTTPException(
            status_code=402,
            detail=f"Your {limits['label']} plan is limited to {limits['max_cameras']} cameras. Upgrade to add more.",
        )

    camera = Camera(org_id=admin.org_id, **body.model_dump())
    await db.cameras.insert_one(camera.model_dump())
    # The site's edge agent picks this up on its next config poll.
    return camera


@router.delete("/{camera_id}")
async def remove_camera(camera_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    result = await db.cameras.delete_one({"camera_id": camera_id, "org_id": admin.org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"status": "deleted"}


@router.post("/test-connection")
async def test_connection(body: dict, _admin: UserPublic = Depends(require_admin)):
    target = body.get("ip_address") or body.get("stream_url") or ""
    if not target:
        raise HTTPException(status_code=400, detail="ip_address or stream_url required")

    # Validate + resolve before probing so this endpoint can't be used as an
    # internal port scanner / cloud-metadata fetcher (SSRF). assert_safe_target
    # returns the resolved-safe host, so the probe below can't be rebound.
    try:
        host, port, _scheme = assert_safe_target(target)
    except UnsafeTargetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    def _probe():
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            return False

    loop = asyncio.get_event_loop()
    reachable = await loop.run_in_executor(None, _probe)
    return {"reachable": reachable, "host": host, "port": port}


@router.patch("/{camera_id}/toggle")
async def toggle_camera(camera_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    cam = await db.cameras.find_one({"camera_id": camera_id, "org_id": admin.org_id})
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    new_state = not cam["enabled"]
    await db.cameras.update_one({"camera_id": camera_id}, {"$set": {"enabled": new_state}})
    # The edge agent starts/stops this camera on its next config poll.
    return {"camera_id": camera_id, "enabled": new_state}
