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


# ── Deployment mode (how the customer runs FiremeX) ─────────────────────────

async def test_deployment_mode_defaults_to_unset(client):
    """A brand-new org has not answered the setup questionnaire, which is what
    sends the admin to the choice screen instead of a guess."""
    await signup(client)
    res = await client.get("/organizations/me")
    assert res.status_code == 200
    assert res.json()["deployment_mode"] == "unset"


async def test_deployment_mode_can_be_set_and_persists(client):
    await signup(client)
    res = await client.put("/organizations/me/deployment-mode",
                           json={"deployment_mode": "home_assistant"})
    assert res.status_code == 200
    assert res.json()["deployment_mode"] == "home_assistant"

    # and it is a property of the org, not of this response
    res = await client.get("/organizations/me")
    assert res.json()["deployment_mode"] == "home_assistant"


async def test_deployment_mode_is_switchable(client):
    """Someone who trials the add-on and then buys dedicated hardware must be
    able to move across without support."""
    await signup(client)
    await client.put("/organizations/me/deployment-mode",
                     json={"deployment_mode": "home_assistant"})
    res = await client.put("/organizations/me/deployment-mode",
                           json={"deployment_mode": "edge"})
    assert res.status_code == 200
    assert res.json()["deployment_mode"] == "edge"


async def test_deployment_mode_rejects_unknown_value(client):
    await signup(client)
    res = await client.put("/organizations/me/deployment-mode",
                           json={"deployment_mode": "kubernetes"})
    assert res.status_code == 422


async def test_deployment_mode_requires_authentication(client):
    res = await client.put("/organizations/me/deployment-mode",
                           json={"deployment_mode": "edge"})
    assert res.status_code == 401
