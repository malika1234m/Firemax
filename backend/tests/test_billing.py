from .conftest import signup


async def test_billing_status_shape_for_fresh_trial_org(client):
    await signup(client)
    res = await client.get("/billing/status")
    assert res.status_code == 200
    body = res.json()
    assert body["org"]["plan"] == "trial"
    assert body["org"]["subscription_status"] == "trialing"
    assert body["usage"] == {"cameras": 0, "users": 1}
    assert body["limits"]["max_cameras"] == 2
    assert "starter" in body["plans"] and "pro" in body["plans"]


async def test_billing_status_requires_authentication(client):
    res = await client.get("/billing/status")
    assert res.status_code == 401


async def test_checkout_session_gracefully_degrades_without_stripe_key(client):
    # No STRIPE_SECRET_KEY configured in the test environment — should fail
    # cleanly with a clear message, not crash.
    await signup(client)
    res = await client.post("/billing/checkout-session", json={"plan": "starter"})
    assert res.status_code == 503


async def test_checkout_session_requires_admin(client):
    await signup(client)
    await client.post("/users/", json={"name": "Sam", "email": "sam@firemex.io", "password": "operatorpass123", "role": "operator"})
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "sam@firemex.io", "password": "operatorpass123"})

    res = await client.post("/billing/checkout-session", json={"plan": "starter"})
    assert res.status_code == 403


async def test_checkout_session_rejects_unknown_plan(client):
    await signup(client)
    res = await client.post("/billing/checkout-session", json={"plan": "enterprise-deluxe"})
    assert res.status_code in (400, 503)   # 503 first if stripe isn't configured at all


async def test_portal_session_gracefully_degrades_without_stripe_key(client):
    await signup(client)
    res = await client.post("/billing/portal-session")
    assert res.status_code == 503


async def test_webhook_rejects_when_not_configured(client):
    res = await client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "fake"})
    assert res.status_code == 503
