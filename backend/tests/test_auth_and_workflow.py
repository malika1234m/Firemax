from app.models import Alert

from .conftest import signup


async def make_alert(db, org_id, **overrides):
    alert = Alert(
        org_id=org_id,
        camera_id="test-cam",
        camera_name="Test Cam",
        hazard_type="fire",
        confidence=0.9,
        zone="Warehouse A",
        **overrides,
    )
    await db.alerts.insert_one(alert.model_dump())
    return alert


# ── Signup / login ──────────────────────────────────────────────────────────

async def test_signup_creates_new_org_and_admin(client):
    res = await signup(client)
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "admin"
    assert body["org_id"]


async def test_two_signups_create_two_separate_orgs(client):
    res1 = await signup(client, org_name="Org One", email="a@firemex.io")
    res2 = await signup(client, org_name="Org Two", email="b@firemex.io")
    assert res1.json()["org_id"] != res2.json()["org_id"]


async def test_admin_created_user_becomes_operator_in_same_org(client):
    admin_res = await signup(client)
    org_id = admin_res.json()["org_id"]

    res = await client.post("/users/", json={
        "name": "Sam Rivera", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator",
    })
    assert res.status_code == 200
    assert res.json()["role"] == "operator"
    assert res.json()["org_id"] == org_id


async def test_duplicate_email_signup_is_rejected(client):
    await signup(client)
    res = await signup(client, name="Someone Else", org_name="Another Org")
    assert res.status_code == 409


async def test_login_with_wrong_password_fails(client):
    await signup(client)
    res = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "wrongpass"})
    assert res.status_code == 401


async def test_login_with_correct_password_succeeds(client):
    await signup(client)
    await client.post("/auth/logout")
    res = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "testpass123"})
    assert res.status_code == 200
    assert res.json()["email"] == "jordan@firemex.io"


async def test_me_requires_authentication(client):
    res = await client.get("/auth/me")
    assert res.status_code == 401


async def test_me_returns_current_user_after_login(client):
    await signup(client)
    res = await client.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["name"] == "Jordan Soto"


async def test_login_rate_limit_kicks_in(client):
    for _ in range(8):
        res = await client.post("/auth/login", json={"email": "nobody@test.io", "password": "wrong"})
        assert res.status_code == 401
    res = await client.post("/auth/login", json={"email": "nobody@test.io", "password": "wrong"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers


# ── RBAC ─────────────────────────────────────────────────────────────────────

async def test_operator_cannot_list_users(client):
    await signup(client)
    await client.post("/users/", json={"name": "Sam", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator"})
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "sam@firemex.io", "password": "operatorpass123"})

    res = await client.get("/users/")
    assert res.status_code == 403


async def test_operator_cannot_add_camera(client):
    await signup(client)
    await client.post("/users/", json={"name": "Sam", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator"})
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "sam@firemex.io", "password": "operatorpass123"})

    res = await client.post("/cameras/", json={"name": "x", "stream_url": "rtsp://x"})
    assert res.status_code == 403


async def test_admin_can_add_and_remove_camera(client):
    await signup(client)
    res = await client.post("/cameras/", json={"name": "Lobby", "stream_url": "rtsp://x/lobby"})
    assert res.status_code == 200
    camera_id = res.json()["camera_id"]

    res = await client.delete(f"/cameras/{camera_id}")
    assert res.status_code == 200


# ── Incident workflow ───────────────────────────────────────────────────────

async def test_promote_to_incident_is_idempotent(client, db):
    admin_res = await signup(client)
    alert = await make_alert(db, admin_res.json()["org_id"])

    res1 = await client.post(f"/alerts/{alert.alert_id}/promote")
    assert res1.status_code == 200
    assert res1.json()["promoted_to_incident"] is True
    first_promoted_at = res1.json()["promoted_at"]

    res2 = await client.post(f"/alerts/{alert.alert_id}/promote")
    assert res2.status_code == 200
    assert res2.json()["promoted_at"] == first_promoted_at   # unchanged — no re-promotion


async def test_promote_requires_authentication(client, db):
    alert = await make_alert(db, "some-org")
    res = await client.post(f"/alerts/{alert.alert_id}/promote")
    assert res.status_code == 401


async def test_resolve_without_verdict_is_rejected(client, db):
    admin_res = await signup(client)
    alert = await make_alert(db, admin_res.json()["org_id"])

    res = await client.patch(f"/alerts/{alert.alert_id}", json={"status": "resolved"})
    assert res.status_code == 400


async def test_resolve_without_remark_is_rejected(client, db):
    admin_res = await signup(client)
    alert = await make_alert(db, admin_res.json()["org_id"])

    res = await client.patch(
        f"/alerts/{alert.alert_id}",
        json={"status": "resolved", "resolution_verdict": "true_fire"},
    )
    assert res.status_code == 400


async def test_resolve_with_verdict_and_remark_succeeds_and_tracks_who(client, db):
    admin_res = await signup(client)
    admin_id = admin_res.json()["user_id"]
    alert = await make_alert(db, admin_res.json()["org_id"])

    res = await client.patch(
        f"/alerts/{alert.alert_id}",
        json={
            "status": "resolved",
            "resolution_verdict": "false_alarm",
            "resolution_remark": "Steam, not smoke.",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "resolved"
    assert body["resolved_by"] == admin_id
    assert body["resolved_at"] is not None


async def test_dead_post_alerts_endpoint_is_gone(client):
    await signup(client)
    res = await client.post("/alerts/", json={})
    assert res.status_code == 405   # method not allowed — GET still exists, POST doesn't


# ── Authority contacts ───────────────────────────────────────────────────────

async def test_authority_contact_rejects_bad_phone_format(client):
    await signup(client)
    res = await client.post("/authorities/", json={"name": "Fire Dept", "phone": "555-1234", "notify_via": "sms"})
    assert res.status_code == 422


async def test_authority_contact_accepts_e164_phone(client):
    await signup(client)
    res = await client.post("/authorities/", json={"name": "Fire Dept", "phone": "+15551234567", "notify_via": "sms"})
    assert res.status_code == 200
