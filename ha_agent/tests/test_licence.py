"""The add-on side of licensing: only a correctly signed answer, issued to THIS
installation and not expired, unlocks more than the free tier.

    backend/.venv/bin/python -m pytest ha_agent/tests -q      (from the repo root)
"""
import base64
import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from ha_agent import licence

KEY = "fmx_test"


@pytest.fixture
def signer(tmp_path, monkeypatch):
    """A throwaway signing key the add-on trusts, and isolated /data files."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setattr(licence, "LICENCE_PUBLIC_KEY", base64.b64encode(public).decode())
    monkeypatch.setattr(licence, "CACHE_PATH", str(tmp_path / "licence.json"))
    monkeypatch.setattr(licence, "INSTALL_ID_PATH", str(tmp_path / "install_id"))

    def sign(install_id, max_cameras=None, exp_in=3600, key=private):
        now = int(time.time())
        payload = json.dumps({"v": 1, "install_id": install_id, "plan": "pro",
                              "max_cameras": max_cameras, "organization": "Acme",
                              "iat": now, "exp": now + exp_in}).encode()
        return {"payload": base64.b64encode(payload).decode(),
                "signature": base64.b64encode(key.sign(payload)).decode()}
    return sign


def cloud(monkeypatch, answer):
    calls = []

    def fake(key, install_id, version):
        calls.append(install_id)
        return answer(install_id) if callable(answer) else answer
    monkeypatch.setattr(licence, "_check_cloud", fake)
    return calls


def test_no_key_is_free_tier():
    assert licence.resolve("")["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_install_id_is_created_once_and_kept(signer):
    first = licence.install_id()
    assert len(first) >= 16
    assert licence.install_id() == first


def test_signed_answer_unlocks_unlimited(signer, monkeypatch):
    calls = cloud(monkeypatch, lambda iid: {"valid": True, "entitlement": signer(iid)})
    result = licence.resolve(KEY)
    assert result["valid"] is True and result["max_cameras"] is None
    assert calls == [licence.install_id()]          # the cloud is told which install


def test_unsigned_valid_answer_is_not_believed(signer, monkeypatch):
    """A home-made licence server can say 'valid' — it cannot sign it."""
    cloud(monkeypatch, {"valid": True, "plan": "pro", "max_cameras": None})
    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_answer_signed_by_another_key_is_not_believed(signer, monkeypatch):
    impostor = Ed25519PrivateKey.generate()
    cloud(monkeypatch, lambda iid: {"valid": True, "entitlement": signer(iid, key=impostor)})
    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_answer_for_another_installation_is_not_believed(signer, monkeypatch):
    """Copying a licensed machine's answer to a second machine does not work."""
    cloud(monkeypatch, lambda iid: {"valid": True, "entitlement": signer("someone-else-0000")})
    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_editing_the_cache_does_not_unlock(signer, monkeypatch):
    cloud(monkeypatch, {"valid": False, "reason": "Subscription is not active"})
    assert licence.resolve(KEY)["max_cameras"] == 1

    # Hand-edit the cache to claim an unlimited licence.
    with open(licence.CACHE_PATH) as fh:
        cache = json.load(fh)
    cache.update(valid=True, plan="pro", max_cameras=None)
    with open(licence.CACHE_PATH, "w") as fh:
        json.dump(cache, fh)

    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_signed_cache_keeps_working_while_cloud_is_down(signer, monkeypatch):
    cloud(monkeypatch, lambda iid: {"valid": True, "entitlement": signer(iid)})
    assert licence.resolve(KEY)["valid"] is True

    # Make the cache stale enough to re-check, then lose the cloud.
    with open(licence.CACHE_PATH) as fh:
        cache = json.load(fh)
    cache["checked_at"] = time.time() - licence.REFRESH_SECONDS - 1
    with open(licence.CACHE_PATH, "w") as fh:
        json.dump(cache, fh)
    cloud(monkeypatch, None)

    result = licence.resolve(KEY)
    assert result["valid"] is True and "cloud unreachable" in result["reason"]


def test_expired_entitlement_drops_to_free_tier_when_offline(signer, monkeypatch):
    cloud(monkeypatch, lambda iid: {"valid": True, "entitlement": signer(iid, exp_in=-1)})
    # Expired on arrival: never granted.
    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS
    cloud(monkeypatch, None)
    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_cloud_down_with_no_cache_is_free_tier_not_zero(signer, monkeypatch):
    cloud(monkeypatch, None)
    assert licence.resolve(KEY)["max_cameras"] == licence.FREE_TIER_MAX_CAMERAS


def test_released_public_key_is_well_formed():
    """The baked-in key must decode to a 32-byte Ed25519 public key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(base64.b64decode(licence.LICENCE_PUBLIC_KEY))
