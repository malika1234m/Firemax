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


async def test_plans_are_sold_by_camera(client):
    plans = {p["plan_id"]: p for p in (await client.get("/billing/plans")).json()["plans"]}
    assert plans["free"]["cameras"] == 1 and plans["trial"]["cameras"] == 4
    assert plans["starter"]["label"] == "Home" and plans["starter"]["cameras"] == 4
    assert plans["pro"]["per_camera"] and (plans["pro"]["min_cameras"], plans["pro"]["max_cameras"]) == (5, 64)
    for p in plans.values():
        # A year costs ten months; one Home Assistant per subscription.
        assert p["price_year_usd"] == p["price_month_usd"] * 10
        assert p["max_installs"] == 1
    assert not any("Live feed" in f for p in plans.values() for f in p["features"])


async def test_plans_from_the_old_catalog_are_replaced_but_new_edits_kept(client, db):
    from app.plans import list_plans, seed_plans
    # A row from the install-based catalog, as production has it.
    await db.plans.insert_one({"plan_id": "pro", "label": "Pro", "price_usd": 199,
                               "max_cameras": 50, "features": ["Up to 5 Home Assistant installations"]})
    plans = {p["plan_id"]: p for p in await list_plans()}
    assert plans["pro"]["price_month_usd"] == 3 and plans["pro"]["per_camera"]
    await db.plans.update_one({"plan_id": "pro"}, {"$set": {"features": ["Our own wording"]}})
    await seed_plans()
    assert (await db.plans.find_one({"plan_id": "pro"}))["features"] == ["Our own wording"]


async def test_installation_times_carry_a_timezone(client):
    await signup(client)
    key = (await client.get("/licence/me")).json()["licence_key"]
    await client.post("/licence/validate",
                      json={"licence_key": key, "install_id": INSTALL, "addon_version": "1.6.0"})
    row = (await client.get("/licence/me/activations")).json()[0]
    assert row["last_seen"].endswith(("Z", "+00:00"))
