"""The website's account features: first-time setup, account activity, and
the access token's status. Activity is about the account only — never cameras
or detections, which live in the customer's Home Assistant."""
from .conftest import signup

INSTALL = "c" * 32


async def _activity(client):
    res = await client.get("/organizations/me/activity")
    assert res.status_code == 200
    return [e["kind"] for e in res.json()]


async def test_a_new_org_has_not_started_setup(client):
    await signup(client)
    org = (await client.get("/organizations/me")).json()
    assert org["onboarding_step"] is None
    assert org["onboarding_completed"] is False


async def test_setup_progress_is_saved_and_resumable(client):
    await signup(client)
    res = await client.put("/organizations/me/onboarding", json={"step": "token"})
    assert res.status_code == 200
    org = (await client.get("/organizations/me")).json()
    assert org["onboarding_step"] == "token"
    assert org["onboarding_completed"] is False
    # Setting up is setting up the Home Assistant add-on.
    assert org["deployment_mode"] == "home_assistant"


async def test_finishing_setup_is_recorded_once(client):
    await signup(client)
    for _ in range(2):
        res = await client.put("/organizations/me/onboarding",
                               json={"step": "done", "completed": True})
        assert res.json()["onboarding_completed"] is True
    assert (await _activity(client)).count("setup_completed") == 1


async def test_unknown_setup_step_is_rejected(client):
    await signup(client)
    res = await client.put("/organizations/me/onboarding", json={"step": "cameras"})
    assert res.status_code == 422


async def test_token_and_connection_events_appear_in_activity(client):
    await signup(client)
    key = (await client.get("/licence/me")).json()["licence_key"]
    await client.post("/licence/validate",
                      json={"licence_key": key, "install_id": INSTALL, "addon_version": "1.6.0"})
    # A second check from the same installation is not a new connection.
    await client.post("/licence/validate",
                      json={"licence_key": key, "install_id": INSTALL, "addon_version": "1.6.0"})
    await client.post("/licence/me/rotate")

    kinds = await _activity(client)
    assert kinds.count("ha_connected") == 1
    assert "token_revoked" in kinds
    assert kinds.count("token_generated") == 2      # first token, then the new one
    assert kinds[0] == "token_generated"            # newest first


async def test_token_status_says_what_the_plan_allows(client, db):
    await signup(client)
    body = (await client.get("/licence/me")).json()
    assert body["entitled"] is True
    assert body["max_installs"] == 1

    await db.organizations.update_many({}, {"$set": {"subscription_status": "canceled"}})
    body = (await client.get("/licence/me")).json()
    assert body["entitled"] is False
    assert body["max_cameras"] == 1


async def test_activity_is_private_to_each_organization(client, client2):
    await signup(client)
    await client.get("/licence/me")
    await signup(client2, org_name="Other Co", email="other@firemex.io")
    assert await _activity(client2) == []
    assert await _activity(client) == ["token_generated"]


async def test_invoices_are_empty_without_a_payment_account(client):
    await signup(client)
    res = await client.get("/billing/invoices")
    assert res.status_code == 200
    assert res.json() == {"invoices": []}


async def test_plans_describe_home_assistant_installations(client):
    plans = {p["plan_id"]: p for p in (await client.get("/billing/plans")).json()["plans"]}
    assert plans["pro"]["max_installs"] == 5
    assert not any("Live feed" in f for p in plans.values() for f in p["features"])


async def test_old_default_plan_features_are_updated_but_edits_kept(client, db):
    from app.plans import seed_plans
    await seed_plans()
    await db.plans.update_one({"plan_id": "trial"}, {"$set": {"features":
        ["Full detection pipeline", "Live feed & incident review", "Email alerts"]}})
    await db.plans.update_one({"plan_id": "pro"}, {"$set": {"features": ["Our own wording"]}})
    await seed_plans()
    trial = await db.plans.find_one({"plan_id": "trial"})
    pro = await db.plans.find_one({"plan_id": "pro"})
    assert "Live feed & incident review" not in trial["features"]
    assert pro["features"] == ["Our own wording"]


async def test_installation_times_carry_a_timezone(client):
    await signup(client)
    key = (await client.get("/licence/me")).json()["licence_key"]
    await client.post("/licence/validate",
                      json={"licence_key": key, "install_id": INSTALL, "addon_version": "1.6.0"})
    row = (await client.get("/licence/me/activations")).json()[0]
    assert row["last_seen"].endswith(("Z", "+00:00"))
