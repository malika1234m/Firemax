from .conftest import signup


# ── Change password ─────────────────────────────────────────────────────────

async def test_change_password_rejects_wrong_current(client):
    await signup(client)
    res = await client.post("/auth/change-password", json={
        "current_password": "wrongpass", "new_password": "newpassword123",
    })
    assert res.status_code == 401


async def test_change_password_success_and_new_password_works(client):
    await signup(client)
    res = await client.post("/auth/change-password", json={
        "current_password": "testpass123", "new_password": "newpassword123",
    })
    assert res.status_code == 200

    await client.post("/auth/logout")
    res = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "newpassword123"})
    assert res.status_code == 200

    # old password no longer works
    await client.post("/auth/logout")
    res = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "testpass123"})
    assert res.status_code == 401


async def test_change_password_requires_authentication(client):
    res = await client.post("/auth/change-password", json={
        "current_password": "x", "new_password": "newpassword123",
    })
    assert res.status_code == 401


# ── Notification preferences ────────────────────────────────────────────────

async def test_notification_prefs_default(client):
    res = await signup(client)
    assert res.json()["notification_prefs"] == {"push": True, "sms": True, "email": False}


async def test_notification_prefs_persist(client):
    await signup(client)
    res = await client.patch("/users/me/preferences", json={"email": True, "sms": False})
    assert res.status_code == 200
    assert res.json()["notification_prefs"] == {"push": True, "sms": False, "email": True}

    # persists across requests
    res = await client.get("/auth/me")
    assert res.json()["notification_prefs"] == {"push": True, "sms": False, "email": True}


# ── Organization settings ───────────────────────────────────────────────────

async def test_org_update_requires_admin(client):
    await signup(client)
    await client.post("/users/", json={"name": "Sam", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator"})
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "sam@firemex.io", "password": "operatorpass123"})

    res = await client.patch("/organizations/me", json={"name": "Hacked Inc"})
    assert res.status_code == 403


async def test_org_update_name_and_detection_settings(client):
    await signup(client)
    res = await client.patch("/organizations/me", json={
        "name": "Renamed Co", "confidence_threshold": 0.75, "alert_cooldown_seconds": 60,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Renamed Co"
    assert body["confidence_threshold"] == 0.75
    assert body["alert_cooldown_seconds"] == 60


async def test_org_update_rejects_out_of_range_confidence(client):
    await signup(client)
    res = await client.patch("/organizations/me", json={"confidence_threshold": 1.5})
    assert res.status_code == 422


async def test_org_update_rejects_out_of_range_cooldown(client):
    await signup(client)
    res = await client.patch("/organizations/me", json={"alert_cooldown_seconds": 2})
    assert res.status_code == 422
