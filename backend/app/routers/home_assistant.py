import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.models import UserPublic, HAConfigUpdate
from app.security import get_current_user, require_admin
from app.crypto import encrypt_secret, decrypt_secret, encryption_available
from app.net_guard import assert_safe_target, UnsafeTargetError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ha", tags=["home-assistant"])

# Entity domains we expose as controllable "devices" in the UI.
# input_boolean is included so a Home Assistant "Toggle" helper (a virtual
# on/off switch you can create in the HA UI with no hardware) works too —
# handy for testing/demo and for automation flags an operator may flip.
CONTROLLABLE_DOMAINS = {"light", "switch", "fan", "lock", "cover", "climate", "input_boolean"}

# domain → (service to turn on/open, service to turn off/close)
TOGGLE_SERVICES = {
    "light":         ("turn_on", "turn_off"),
    "switch":        ("turn_on", "turn_off"),
    "fan":           ("turn_on", "turn_off"),
    "lock":          ("unlock", "lock"),
    "cover":         ("open_cover", "close_cover"),
    "climate":       ("turn_on", "turn_off"),
    "input_boolean": ("turn_on", "turn_off"),
}

ON_STATES = {"on", "unlocked", "open", "heat", "cool"}


async def _load_org_ha(org_id: str) -> tuple[str | None, str | None]:
    """Return (ha_url, ha_token) for an org, decrypting the stored token.
    Either value is None when HA isn't configured for that org."""
    db = get_db()
    org = await db.organizations.find_one({"org_id": org_id})
    if not org:
        return None, None
    url = org.get("ha_url") or None
    enc = org.get("ha_token_encrypted")
    token = decrypt_secret(enc) if enc else None
    return url, token


def _headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Per-org connection config (admin only) ──────────────────────────────────

@router.get("/config")
async def get_ha_config(admin: UserPublic = Depends(require_admin)):
    url, token = await _load_org_ha(admin.org_id)
    # Never return the token itself — only whether one is stored.
    return {"ha_url": url or "", "configured": bool(url and token), "encryption_available": encryption_available()}


@router.put("/config")
async def set_ha_config(body: HAConfigUpdate, admin: UserPublic = Depends(require_admin)):
    if not encryption_available():
        raise HTTPException(
            status_code=503,
            detail="Secret encryption isn't configured on this server (SECRETS_ENCRYPTION_KEY). "
                   "HA credentials can't be stored securely until it is.",
        )
    # SSRF guard: the URL is admin-supplied and we make server-side requests to
    # it, so refuse the link-local metadata range and non-http(s) schemes.
    # Loopback is allowed here because HA legitimately runs on the same host
    # (localhost) in on-prem/local deployments.
    try:
        assert_safe_target(body.ha_url, allow_loopback=True)
    except UnsafeTargetError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Home Assistant URL: {exc}")

    db = get_db()
    await db.organizations.update_one(
        {"org_id": admin.org_id},
        {"$set": {"ha_url": body.ha_url.rstrip("/"), "ha_token_encrypted": encrypt_secret(body.ha_token)}},
    )
    return {"status": "saved", "configured": True}


@router.delete("/config")
async def clear_ha_config(admin: UserPublic = Depends(require_admin)):
    db = get_db()
    await db.organizations.update_one(
        {"org_id": admin.org_id}, {"$set": {"ha_url": "", "ha_token_encrypted": None}}
    )
    return {"status": "cleared"}


# ── Device control (scoped to the caller's org HA) ──────────────────────────

@router.get("/status")
async def ha_status(user: UserPublic = Depends(get_current_user)):
    url, token = await _load_org_ha(user.org_id)
    if not url or not token:
        return {"connected": False, "reason": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{url}/api/", headers=_headers(token))
            return {"connected": r.status_code == 200}
    except Exception:
        return {"connected": False, "reason": "unreachable"}


@router.get("/entities")
async def list_entities(user: UserPublic = Depends(get_current_user)):
    url, token = await _load_org_ha(user.org_id)
    if not url or not token:
        raise HTTPException(status_code=503, detail="Home Assistant is not configured for your organization")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(f"{url}/api/states", headers=_headers(token))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Home Assistant: {exc}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Home Assistant rejected the request — check the token")

    entities = []
    for e in r.json():
        domain = e["entity_id"].split(".")[0]
        if domain not in CONTROLLABLE_DOMAINS:
            continue
        entities.append({
            "entity_id": e["entity_id"],
            "domain": domain,
            "name": e.get("attributes", {}).get("friendly_name", e["entity_id"]),
            "state": e["state"],
            "is_on": e["state"] in ON_STATES,
        })
    return sorted(entities, key=lambda x: x["name"])


@router.post("/entities/{entity_id}/toggle")
async def toggle_entity(entity_id: str, user: UserPublic = Depends(get_current_user)):
    url, token = await _load_org_ha(user.org_id)
    if not url or not token:
        raise HTTPException(status_code=503, detail="Home Assistant is not configured for your organization")
    domain = entity_id.split(".")[0]
    if domain not in TOGGLE_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unsupported domain: {domain}")

    async with httpx.AsyncClient(timeout=6.0) as client:
        state_r = await client.get(f"{url}/api/states/{entity_id}", headers=_headers(token))
        if state_r.status_code != 200:
            raise HTTPException(status_code=404, detail="Entity not found")
        current_on = state_r.json()["state"] in ON_STATES

        on_service, off_service = TOGGLE_SERVICES[domain]
        service = off_service if current_on else on_service

        call_r = await client.post(
            f"{url}/api/services/{domain}/{service}",
            headers=_headers(token),
            json={"entity_id": entity_id},
        )
        if call_r.status_code >= 300:
            raise HTTPException(status_code=502, detail="Home Assistant rejected the service call")

    return {"entity_id": entity_id, "is_on": not current_on}
