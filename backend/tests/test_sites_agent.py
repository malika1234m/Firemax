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
    cam = (await client.post("/cameras/", json={"name": "Bay 1", "stream_url": "rtsp://10.0.0.5"})).json()
    await client.post("/agent/events", headers=AGENT(token),
                      json=[{"camera_id": cam["camera_id"], "camera_name": "Bay 1",
                             "hazard_type": "fire", "confidence": 0.97, "zone": "A"}])
    db = get_db()
    alert = await db.alerts.find_one({"camera_name": "Bay 1"})
    assert alert is not None and alert["org_id"] == org_id and alert["hazard_type"] == "fire"


async def test_events_for_deleted_camera_are_ignored(client):
    """An agent keeps its camera list until restarted, so it goes on reporting
    for cameras that have since been deleted. Those must not become alerts —
    otherwise incidents appear for a camera the operator can no longer see."""
    await signup(client)
    _, token = await _create_site(client)
    cam = (await client.post("/cameras/", json={"name": "Gone", "stream_url": "rtsp://10.0.0.6"})).json()
    await client.delete(f"/cameras/{cam['camera_id']}")

    body = await client.post("/agent/events", headers=AGENT(token),
                             json=[{"camera_id": cam["camera_id"], "camera_name": "Gone",
                                    "hazard_type": "fire", "confidence": 0.9, "zone": "A"}])
    assert body.json() == {"status": "ok", "created": 0, "ignored": 1}
    assert await get_db().alerts.find_one({"camera_name": "Gone"}) is None


async def test_selftest_event_is_always_accepted(client):
    """`agent.py --selftest` posts an event before any camera exists; that is
    how a site is commissioned, so it must bypass the camera check."""
    await signup(client)
    _, token = await _create_site(client)
    body = await client.post("/agent/events", headers=AGENT(token),
                             json=[{"camera_id": "selftest", "camera_name": "Self-Test Camera",
                                    "hazard_type": "smoke", "confidence": 0.42, "zone": "Self-Test"}])
    assert body.json()["created"] == 1


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


# ── Camera liveness ──────────────────────────────────────────────────────────

async def test_camera_health_is_not_derived_from_enabled(client):
    """A camera can be enabled for months with no agent anywhere. The dashboard
    used to count `enabled` cameras as online and tell a customer with nothing
    running that all cameras were reporting."""
    await signup(client)
    cam = (await client.post("/cameras/", json={"name": "Bay", "stream_url": "rtsp://10.0.0.9"})).json()

    health = (await client.get("/cameras/health")).json()
    entry = health["cameras"][cam["camera_id"]]
    assert entry["enabled"] is True          # operator switched it on …
    assert entry["online"] is False          # … but nothing is watching it
    assert entry["reported"] is False        # no agent has ever mentioned it
    assert health["online"] == 0


async def test_camera_health_reflects_agent_heartbeat(client):
    await signup(client)
    cam = (await client.post("/cameras/", json={"name": "Bay", "stream_url": "rtsp://10.0.0.9"})).json()
    _, token = await _create_site(client)

    await client.post("/agent/heartbeat", headers=AGENT(token), json={
        "agent_version": "0.1.0",
        "pipelines": [{"camera_id": cam["camera_id"], "fps": 4.2, "inference_ms": 120, "online": True}],
    })

    health = (await client.get("/cameras/health")).json()
    entry = health["cameras"][cam["camera_id"]]
    assert entry["online"] is True and entry["reported"] is True and entry["fps"] == 4.2
    assert health["online"] == 1
