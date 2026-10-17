"""Licensing for the fully-local Home Assistant add-on."""
import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.licence_signing import public_key_b64

from .conftest import signup

INSTALL_A = "a" * 32
INSTALL_B = "b" * 32


def _check(key, install_id=INSTALL_A):
    return {"licence_key": key, "install_id": install_id, "addon_version": "1.3.0"}


def _claims(entitlement):
    """Verify the signed entitlement exactly as the add-on does."""
    payload = base64.b64decode(entitlement["payload"])
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64())).verify(
        base64.b64decode(entitlement["signature"]), payload)
    return json.loads(payload)


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

    res = await client.post("/licence/validate", json=_check(key))
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["max_cameras"] is None          # unlimited
    assert body["organization"] == "Acme Fire Safety"

    claims = _claims(body["entitlement"])
    assert claims["install_id"] == INSTALL_A
    assert claims["max_cameras"] is None
    assert claims["exp"] > claims["iat"]


async def test_validate_needs_no_session(client, client2):
    """An add-on in the field has no account — the key is the whole credential."""
    await signup(client)
    key = await _key(client)

    # client2 has its own cookie jar and has never logged in.
    res = await client2.post("/licence/validate", json=_check(key))
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

    res = await client.post("/licence/validate", json=_check(key))
    body = res.json()
    assert body["valid"] is False
    assert body["max_cameras"] == 1
    assert body["entitlement"] is None


async def test_rotation_invalidates_the_old_key(client):
    await signup(client)
    old = await _key(client)

    res = await client.post("/licence/me/rotate")
    assert res.status_code == 200
    new = res.json()["licence_key"]
    assert new != old

    assert (await client.post("/licence/validate", json=_check(old))).json()["valid"] is False
    assert (await client.post("/licence/validate", json=_check(new))).json()["valid"] is True


async def test_licence_key_is_not_exposed_on_the_org_payload(client):
    """It is a bearer credential — every signed-in user can read /organizations/me."""
    await signup(client)
    await _key(client)                      # force one to exist
    res = await client.get("/organizations/me")
    assert "licence_key" not in res.json()


async def test_licence_endpoints_require_admin(client):
    res = await client.get("/licence/me")
    assert res.status_code == 401


async def test_old_addon_without_install_id_gets_free_tier_and_a_reason(client):
    """Add-ons before 1.3.0 send no installation id, so they cannot be held to
    the installation limit — free tier, never zero, and told to update."""
    await signup(client)
    key = await _key(client)
    body = (await client.post("/licence/validate", json={"licence_key": key})).json()
    assert body["valid"] is False
    assert body["max_cameras"] == 1
    assert "1.3.0" in body["reason"]


async def test_same_installation_checking_again_keeps_its_seat(client):
    await signup(client)
    key = await _key(client)
    for _ in range(3):
        assert (await client.post("/licence/validate", json=_check(key))).json()["valid"] is True
    assert len((await client.get("/licence/me/activations")).json()) == 1


async def test_shared_key_is_refused_on_an_extra_installation(client):
    """A trial allows one installation: a second machine using the same key
    falls back to the free tier and is told why."""
    await signup(client)
    key = await _key(client)
    assert (await client.post("/licence/validate", json=_check(key, INSTALL_A))).json()["valid"] is True

    body = (await client.post("/licence/validate", json=_check(key, INSTALL_B))).json()
    assert body["valid"] is False
    assert body["max_cameras"] == 1
    assert "already active" in body["reason"]


async def test_owner_sees_and_removes_an_installation(client):
    await signup(client)
    key = await _key(client)
    await client.post("/licence/validate", json=_check(key, INSTALL_A))

    rows = (await client.get("/licence/me/activations")).json()
    assert [r["install_id"] for r in rows] == [INSTALL_A]
    assert rows[0]["addon_version"] == "1.3.0"

    assert (await client.delete(f"/licence/me/activations/{INSTALL_A}")).status_code == 204
    assert (await client.get("/licence/me/activations")).json() == []

    # The removed machine cannot take its seat back with the same key...
    body = (await client.post("/licence/validate", json=_check(key, INSTALL_A))).json()
    assert body["valid"] is False
    assert "removed" in body["reason"]
    # ...but the freed seat is available to a different installation.
    assert (await client.post("/licence/validate", json=_check(key, INSTALL_B))).json()["valid"] is True


async def test_removing_an_unknown_installation_is_404(client):
    await signup(client)
    assert (await client.delete(f"/licence/me/activations/{INSTALL_A}")).status_code == 404


async def test_rotation_frees_every_seat(client):
    await signup(client)
    old = await _key(client)
    await client.post("/licence/validate", json=_check(old, INSTALL_A))
    new = (await client.post("/licence/me/rotate")).json()["licence_key"]
    assert (await client.get("/licence/me/activations")).json() == []
    assert (await client.post("/licence/validate", json=_check(new, INSTALL_B))).json()["valid"] is True


async def test_installations_are_private_to_their_organization(client, client2):
    await signup(client)
    key = await _key(client)
    await client.post("/licence/validate", json=_check(key, INSTALL_A))

    await signup(client2, org_name="Other Co", email="other@firemex.io")
    assert (await client2.get("/licence/me/activations")).json() == []
    assert (await client2.delete(f"/licence/me/activations/{INSTALL_A}")).status_code == 404


async def test_malformed_install_id_is_rejected(client):
    res = await client.post("/licence/validate",
                            json={"licence_key": "fmx_x", "install_id": "../../etc"})
    assert res.status_code == 422
