"""Signed licence entitlements for the Home Assistant add-on.

A licence answer is only useful to the add-on if it cannot be forged on the
customer's own machine. The add-on caches the cloud's answer in /data so it
keeps working offline, and before this the cache was plain JSON: editing it to
say "valid, unlimited" was enough. Pointing the add-on at a home-made licence
server worked too.

So the cloud signs what it grants with an Ed25519 private key that never leaves
the cloud, and the add-on verifies it with the matching public key baked into
its image (ha_agent/licence.py). An edited cache or a fake server cannot produce
a valid signature.

The entitlement also names the installation it was issued to, so copying the
cache file to a second machine does not license that machine.

    LICENCE_SIGNING_KEY   base64 of the 32-byte Ed25519 private key. Generate:
      python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
    then derive the public key with public_key_b64() and put it in the add-on.
"""
import base64
import json
import logging
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.config import settings

logger = logging.getLogger("licence")

# How long a signed entitlement stays valid without the add-on reaching us.
# This IS the add-on's offline grace: a site whose uplink is down, or that is
# deliberately kept offline after setup, keeps its cameras this long. The add-on
# re-checks weekly when it can, so a revoked or cancelled licence is noticed
# within a week on any machine that is online.
ENTITLEMENT_SECONDS = 60 * 24 * 3600

_key: Ed25519PrivateKey | None = None


def _private_key() -> Ed25519PrivateKey:
    global _key
    if _key is None:
        if settings.LICENCE_SIGNING_KEY:
            _key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(settings.LICENCE_SIGNING_KEY))
        else:
            # Development only. Entitlements signed with a throwaway key fail
            # verification in a real add-on, which then falls back to the free
            # tier — loud in the add-on log, never a silent grant.
            logger.warning("LICENCE_SIGNING_KEY is not set — signing licences with a "
                           "temporary key that no released add-on will accept")
            _key = Ed25519PrivateKey.generate()
    return _key


def public_key_b64() -> str:
    raw = _private_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def sign_entitlement(install_id: str, plan: str, max_cameras: int | None,
                     organization: str | None) -> dict:
    """The signed part of a licence answer: {payload, signature}, both base64.

    The payload is signed as exact bytes and verified as the same bytes, so no
    JSON canonicalisation has to agree between the two sides."""
    now = int(time.time())
    payload = json.dumps({
        "v": 1,
        "install_id": install_id,
        "plan": plan,
        "max_cameras": max_cameras,
        "organization": organization,
        "iat": now,
        "exp": now + ENTITLEMENT_SECONDS,
    }, separators=(",", ":")).encode()
    return {
        "payload": base64.b64encode(payload).decode(),
        "signature": base64.b64encode(_private_key().sign(payload)).decode(),
    }
