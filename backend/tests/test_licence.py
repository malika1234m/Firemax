"""Licensing for the fully-local Home Assistant add-on."""
from .conftest import signup


async def _key(client) -> str:
    res = await client.get("/licence/me")
    assert res.status_code == 200
    return res.json()["licence_key"]


async def test_admin_gets_a_key_minted_on_first_request(client):
    await signup(client)
    res = await client.get("/licence/me")
    assert res.status_code == 200
    body = res.json()
    assert body["licence_key"].startswith("fmx_")
    # A fresh org is trialing, which is an entitled state.
    assert body["max_cameras"] is None


async def test_key_is_stable_across_requests(client):
    await signup(client)
    assert await _key(client) == await _key(client)


async def test_valid_key_unlocks_unlimited_cameras(client):
    await signup(client)
    key = await _key(client)

    res = await client.post("/licence/validate", json={"licence_key": key})
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["max_cameras"] is None          # unlimited
    assert body["organization"] == "Acme Fire Safety"


async def test_validate_needs_no_session(client, client2):
    """An add-on in the field has no account — the key is the whole credential."""
    await signup(client)
    key = await _key(client)

    # client2 has its own cookie jar and has never logged in.
    res = await client2.post("/licence/validate", json={"licence_key": key})
    assert res.status_code == 200
    assert res.json()["valid"] is True


async def test_unknown_key_falls_back_to_free_tier(client):
    res = await client.post("/licence/validate", json={"licence_key": "fmx_nonsense"})
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False
    assert body["max_cameras"] == 1             # free tier, not zero
    # Must not reveal whether the key named a real organization.
    assert body["organization"] is None


async def test_empty_key_is_free_tier_not_an_error(client):
    """A brand-new add-on starts with no key. That is the free tier, not a
    failure — it must still watch one camera."""
    res = await client.post("/licence/validate", json={"licence_key": ""})
    assert res.status_code == 200
    assert res.json()["valid"] is False
    assert res.json()["max_cameras"] == 1


async def test_cancelled_subscription_loses_entitlement(client, db):
    await signup(client)
    key = await _key(client)
    await db.organizations.update_one({"licence_key": key},
                                      {"$set": {"subscription_status": "canceled"}})

    res = await client.post("/licence/validate", json={"licence_key": key})
    body = res.json()
    assert body["valid"] is False
    assert body["max_cameras"] == 1


async def test_rotation_invalidates_the_old_key(client):
    await signup(client)
    old = await _key(client)

    res = await client.post("/licence/me/rotate")
    assert res.status_code == 200
    new = res.json()["licence_key"]
    assert new != old

    assert (await client.post("/licence/validate", json={"licence_key": old})).json()["valid"] is False
    assert (await client.post("/licence/validate", json={"licence_key": new})).json()["valid"] is True


async def test_licence_key_is_not_exposed_on_the_org_payload(client):
    """It is a bearer credential — every signed-in user can read /organizations/me."""
    await signup(client)
    await _key(client)                      # force one to exist
    res = await client.get("/organizations/me")
    assert "licence_key" not in res.json()


async def test_licence_endpoints_require_admin(client):
    res = await client.get("/licence/me")
    assert res.status_code == 401
