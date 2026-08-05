import pytest
from cryptography.fernet import Fernet
from app.config import settings
from app.database import get_db
from .conftest import signup


@pytest.fixture(autouse=True)
def ensure_encryption_key():
    # Guarantee a key exists so these tests are deterministic even without .env.
    if not settings.SECRETS_ENCRYPTION_KEY:
        settings.SECRETS_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield


async def test_ha_config_defaults_to_unconfigured(client):
    await signup(client)
    res = await client.get("/ha/config")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert body["ha_url"] == ""


async def test_set_ha_config_stores_token_encrypted(client):
    await signup(client)
    res = await client.put("/ha/config", json={"ha_url": "http://192.168.1.10:8123", "ha_token": "super-secret-token"})
    assert res.status_code == 200

    # The plaintext token must never be returned by the API.
    cfg = (await client.get("/ha/config")).json()
    assert cfg["configured"] is True
    assert cfg["ha_url"] == "http://192.168.1.10:8123"
    assert "super-secret-token" not in str(cfg)

    # At rest it must be encrypted, not plaintext.
    db = get_db()
    org = await db.organizations.find_one({"ha_url": "http://192.168.1.10:8123"})
    assert org["ha_token_encrypted"] != "super-secret-token"
    assert org["ha_token_encrypted"]  # present


async def test_set_ha_config_rejects_link_local_metadata(client):
    # The cloud-metadata range must stay blocked even though loopback is allowed.
    await signup(client)
    res = await client.put("/ha/config", json={"ha_url": "http://169.254.169.254", "ha_token": "t"})
    assert res.status_code == 400


async def test_set_ha_config_allows_localhost(client):
    # HA commonly runs on the same host (on-prem / local dev), so loopback is OK.
    await signup(client)
    res = await client.put("/ha/config", json={"ha_url": "http://localhost:8123", "ha_token": "t"})
    assert res.status_code == 200


async def test_set_ha_config_requires_admin(client):
    await signup(client)
    # add an operator, log in as them
    await client.post("/users/", json={"name": "Op", "email": "op@firemex.io", "password": "operatorpass123", "role": "operator"})
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "op@firemex.io", "password": "operatorpass123"})
    res = await client.put("/ha/config", json={"ha_url": "http://192.168.1.10:8123", "ha_token": "t"})
    assert res.status_code == 403


async def test_ha_config_is_org_scoped(client, client2):
    # Org A configures HA; Org B must not see it.
    await signup(client, org_name="Org A", email="a@firemex.io")
    await signup(client2, org_name="Org B", email="b@firemex.io")

    await client.put("/ha/config", json={"ha_url": "http://192.168.1.10:8123", "ha_token": "a-token"})

    a_cfg = (await client.get("/ha/config")).json()
    b_cfg = (await client2.get("/ha/config")).json()
    assert a_cfg["configured"] is True
    assert b_cfg["configured"] is False
    assert b_cfg["ha_url"] == ""


async def test_clear_ha_config(client):
    await signup(client)
    await client.put("/ha/config", json={"ha_url": "http://192.168.1.10:8123", "ha_token": "t"})
    assert (await client.delete("/ha/config")).status_code == 200
    assert (await client.get("/ha/config")).json()["configured"] is False
