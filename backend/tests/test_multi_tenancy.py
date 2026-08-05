from app.models import Alert
from .conftest import signup


async def make_alert(db, org_id, **overrides):
    fields = {
        "org_id": org_id, "camera_id": "test-cam", "camera_name": "Test Cam",
        "hazard_type": "fire", "confidence": 0.9, "zone": "Warehouse A",
    }
    fields.update(overrides)
    alert = Alert(**fields)
    await db.alerts.insert_one(alert.model_dump())
    return alert


async def two_orgs(client, client2):
    """Sign up two independent companies, each with their own admin session."""
    res_a = await signup(client, org_name="Org A", email="admin-a@firemex.io")
    res_b = await signup(client2, org_name="Org B", email="admin-b@firemex.io")
    return res_a.json(), res_b.json()


# ── Cameras ──────────────────────────────────────────────────────────────────

async def test_camera_list_is_scoped_to_own_org(client, client2):
    await two_orgs(client, client2)
    await client.post("/cameras/", json={"name": "Org A Cam", "stream_url": "rtsp://a"})
    await client2.post("/cameras/", json={"name": "Org B Cam", "stream_url": "rtsp://b"})

    res_a = await client.get("/cameras/")
    res_b = await client2.get("/cameras/")
    assert [c["name"] for c in res_a.json()] == ["Org A Cam"]
    assert [c["name"] for c in res_b.json()] == ["Org B Cam"]


async def test_cannot_delete_another_orgs_camera(client, client2):
    await two_orgs(client, client2)
    res = await client.post("/cameras/", json={"name": "Org A Cam", "stream_url": "rtsp://a"})
    camera_id = res.json()["camera_id"]

    res = await client2.delete(f"/cameras/{camera_id}")
    assert res.status_code == 404

    # still visible to its actual owner
    res = await client.get("/cameras/")
    assert len(res.json()) == 1


# ── Alerts ───────────────────────────────────────────────────────────────────

async def test_alert_list_is_scoped_to_own_org(client, client2, db):
    org_a, org_b = await two_orgs(client, client2)
    await make_alert(db, org_a["org_id"], hazard_type="fire")
    await make_alert(db, org_b["org_id"], hazard_type="smoke")

    res_a = await client.get("/alerts/")
    res_b = await client2.get("/alerts/")
    assert [a["hazard_type"] for a in res_a.json()] == ["fire"]
    assert [a["hazard_type"] for a in res_b.json()] == ["smoke"]


async def test_cannot_promote_another_orgs_alert(client, client2, db):
    org_a, _ = await two_orgs(client, client2)
    alert = await make_alert(db, org_a["org_id"])

    res = await client2.post(f"/alerts/{alert.alert_id}/promote")
    assert res.status_code == 404


# ── Users ────────────────────────────────────────────────────────────────────

async def test_user_list_is_scoped_to_own_org(client, client2):
    org_a, org_b = await two_orgs(client, client2)

    res_a = await client.get("/users/")
    res_b = await client2.get("/users/")
    assert [u["org_id"] for u in res_a.json()] == [org_a["org_id"]]
    assert [u["org_id"] for u in res_b.json()] == [org_b["org_id"]]


async def test_cannot_delete_another_orgs_user(client, client2):
    await two_orgs(client, client2)
    add_res = await client.post("/users/", json={
        "name": "Sam", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator",
    })
    user_id = add_res.json()["user_id"]

    res = await client2.delete(f"/users/{user_id}")
    assert res.status_code == 404


# ── Shifts ───────────────────────────────────────────────────────────────────

async def test_cannot_assign_shift_to_another_orgs_user(client, client2):
    org_a, _ = await two_orgs(client, client2)
    add_res = await client.post("/users/", json={
        "name": "Sam", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator",
    })
    user_id = add_res.json()["user_id"]

    # org B's admin tries to schedule org A's operator
    res = await client2.post("/shifts/", json={
        "user_id": user_id, "start_time": "2026-08-01T08:00:00", "end_time": "2026-08-01T16:00:00",
    })
    assert res.status_code == 404


# ── Authority contacts ───────────────────────────────────────────────────────

async def test_authority_contacts_scoped_to_own_org(client, client2):
    await two_orgs(client, client2)
    await client.post("/authorities/", json={"name": "Org A FD", "phone": "+15551234567", "notify_via": "sms"})

    res_a = await client.get("/authorities/")
    res_b = await client2.get("/authorities/")
    assert len(res_a.json()) == 1
    assert len(res_b.json()) == 0


# ── Plan limits ──────────────────────────────────────────────────────────────

async def test_camera_plan_limit_enforced(client):
    await signup(client)   # trial plan: max_cameras = 2
    await client.post("/cameras/", json={"name": "Cam 1", "stream_url": "rtsp://1"})
    await client.post("/cameras/", json={"name": "Cam 2", "stream_url": "rtsp://2"})

    res = await client.post("/cameras/", json={"name": "Cam 3", "stream_url": "rtsp://3"})
    assert res.status_code == 402


async def test_user_plan_limit_enforced(client):
    await signup(client)   # trial plan: max_users = 3 (the admin already counts as 1)
    await client.post("/users/", json={"name": "U1", "email": "u1@firemex.io", "password": "operatorpass123"})
    await client.post("/users/", json={"name": "U2", "email": "u2@firemex.io", "password": "operatorpass123"})

    res = await client.post("/users/", json={"name": "U3", "email": "u3@firemex.io", "password": "operatorpass123"})
    assert res.status_code == 402
