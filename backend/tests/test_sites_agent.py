from app.database import get_db
from .conftest import signup

AGENT = lambda tok: {"X-Agent-Token": tok}


async def _create_site(client, name="HQ"):
    res = await client.post("/sites/", json={"name": name})
    assert res.status_code == 200
    body = res.json()
    return body["site"]["site_id"], body["enrollment_token"]


# ── Site enrollment ──────────────────────────────────────────────────────────

async def test_create_site_returns_token_once(client):
    await signup(client)
    sid, token = await _create_site(client)
    assert token and len(token) > 20

    # Listing never exposes the token.
    sites = (await client.get("/sites/")).json()
    assert len(sites) == 1 and sites[0]["site_id"] == sid
    assert "token" not in str(sites[0]).lower() or "token_hash" not in str(sites[0])


async def test_only_admin_can_create_sites(client):
    await signup(client)
    await client.post("/users/", json={"name": "Op", "email": "op@firemex.io", "password": "operatorpass123", "role": "operator"})
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "op@firemex.io", "password": "operatorpass123"})
    assert (await client.post("/sites/", json={"name": "X"})).status_code == 403


async def test_rotate_token_invalidates_old(client):
    await signup(client)
    sid, old = await _create_site(client)
    assert (await client.get("/agent/config", headers=AGENT(old))).status_code == 200

    new = (await client.post(f"/sites/{sid}/rotate-token")).json()["enrollment_token"]
    assert new != old
    assert (await client.get("/agent/config", headers=AGENT(old))).status_code == 401
    assert (await client.get("/agent/config", headers=AGENT(new))).status_code == 200


# ── Agent auth ───────────────────────────────────────────────────────────────

async def test_agent_requires_valid_token(client):
    await signup(client)
    await _create_site(client)
    assert (await client.get("/agent/config")).status_code == 401
    assert (await client.get("/agent/config", headers=AGENT("bogus"))).status_code == 401


async def test_customer_session_cannot_hit_agent_routes(client):
    # A logged-in user cookie is not an agent token.
    await signup(client)
    assert (await client.get("/agent/config")).status_code == 401


# ── Agent config / heartbeat / events ────────────────────────────────────────

async def test_agent_config_returns_cameras_and_settings(client):
    await signup(client)
    _, token = await _create_site(client)
    cfg = (await client.get("/agent/config", headers=AGENT(token))).json()
    assert "cameras" in cfg and "detection" in cfg and "home_assistant" in cfg
    assert cfg["detection"]["confidence_threshold"] == 0.5


async def test_heartbeat_marks_site_online(client):
    await signup(client)
    _, token = await _create_site(client)
    res = await client.post("/agent/heartbeat", headers=AGENT(token),
                            json={"agent_version": "0.1.0", "pipelines": [{"camera_id": "c1", "fps": 5, "online": True}]})
    assert res.status_code == 200
    assert (await client.get("/sites/")).json()[0]["status"] == "online"


async def test_events_create_org_scoped_alerts(client):
    res = await signup(client)
    org_id = res.json()["org_id"]
    _, token = await _create_site(client)
    await client.post("/agent/events", headers=AGENT(token),
                      json=[{"camera_id": "c1", "camera_name": "Bay 1", "hazard_type": "fire", "confidence": 0.97, "zone": "A"}])
    db = get_db()
    alert = await db.alerts.find_one({"camera_name": "Bay 1"})
    assert alert is not None and alert["org_id"] == org_id and alert["hazard_type"] == "fire"


# ── Cross-org isolation ──────────────────────────────────────────────────────

async def test_agent_token_is_org_scoped(client, client2):
    await signup(client, org_name="Org A", email="a@firemex.io")
    await signup(client2, org_name="Org B", email="b@firemex.io")
    # Org A adds a camera; Org B's agent must not receive it.
    await client.post("/cameras/", json={"name": "A Cam", "stream_url": "rtsp://10.0.0.2"})
    _, b_token = await _create_site(client2)
    cfg = (await client2.get("/agent/config", headers=AGENT(b_token))).json()
    assert all(c["name"] != "A Cam" for c in cfg["cameras"])


async def test_cannot_delete_another_orgs_site(client, client2):
    await signup(client, org_name="Org A", email="a@firemex.io")
    await signup(client2, org_name="Org B", email="b@firemex.io")
    sid, _ = await _create_site(client)
    assert (await client2.delete(f"/sites/{sid}")).status_code == 404
