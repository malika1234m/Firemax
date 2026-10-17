"""Licence check for the fully-local add-on.

The add-on has no account and no session, so entitlement is an opaque key the
customer pastes into the Configuration tab. It is checked against the FiremeX
cloud once and then cached in /data, which survives restarts and add-on updates.

Three rules shape everything here, and all three come from what this software
is for:

1. **No key is a valid state, not an error.** A fresh install watches one camera
   and says so. Someone must be able to try FiremeX on their own footage without
   an account.

2. **The network is never allowed to stop detection.** If the cloud is
   unreachable the cached answer is used, even a stale one. A building does not
   become safe because a certificate expired in San Francisco.

3. **The check degrades, never blocks.** The worst outcome of any licensing
   failure is the free tier — one camera still watched — never zero.

Since 1.3.0 a licence is bound to this installation and signed by the cloud:

- On first start the add-on creates a random installation id in /data and sends
  it with every check. The cloud allows each plan a fixed number of
  installations, so a key handed around stops working on the extra machines,
  and the owner sees every installation in the dashboard and can remove one.
- A valid answer carries an Ed25519 signature over {installation id, plan,
  limit, expiry}. The add-on trusts only that signed part, checked with the
  public key below. Editing the cached file, copying it to another machine, or
  pointing the add-on at a home-made licence server all fail verification and
  land on the free tier.

What this cannot stop is someone changing the add-on's own code on their own
hardware. Nothing that runs on a customer's machine can. The aim is to make
paying the easy path, not to fight the owner of the hardware.
"""
import base64
import json
import logging
import os
import time
import uuid

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

logger = logging.getLogger("ha.licence")

# The public API. Overridable so the add-on can be pointed at a staging cloud
# during development without editing the image.
CLOUD_URL = os.environ.get("FIREMEX_CLOUD_URL",
                           "https://firemex-backend.up.railway.app").rstrip("/")

CACHE_PATH = os.environ.get("LICENCE_CACHE_PATH", "/data/licence.json")
INSTALL_ID_PATH = os.environ.get("INSTALL_ID_PATH", "/data/install_id")

# Public half of the cloud's licence-signing key (LICENCE_SIGNING_KEY on the
# backend). Deliberately NOT overridable from the environment: a public key an
# attacker could swap would make the signature check worthless.
LICENCE_PUBLIC_KEY = "396MfhQkVC9XDbg+H69bN7yKzxDtr2ZKOKYedPwgNbU="

# How often a licence is re-checked when the cloud is reachable.
REFRESH_SECONDS = 7 * 24 * 3600

# How long a valid answer keeps working while the cloud is unreachable is set by
# the cloud, as the signed entitlement's expiry (60 days). Generous on purpose: a
# site with a flaky uplink, or one kept off the internet after setup, must not
# silently lose cameras. After that the add-on drops to the free tier — it never
# stops.

FREE_TIER_MAX_CAMERAS = 1


def _free(reason: str) -> dict:
    return {"valid": False, "plan": "free",
            "max_cameras": FREE_TIER_MAX_CAMERAS, "reason": reason}


def install_id() -> str:
    """This installation's id, created once and kept in /data so it survives
    restarts and add-on updates. A reinstall gets a new one — the owner removes
    the old installation from the dashboard."""
    try:
        with open(INSTALL_ID_PATH) as fh:
            value = fh.read().strip()
        if 16 <= len(value) <= 64:
            return value
    except OSError:
        pass
    value = uuid.uuid4().hex
    try:
        os.makedirs(os.path.dirname(INSTALL_ID_PATH), exist_ok=True)
        with open(INSTALL_ID_PATH, "w") as fh:
            fh.write(value)
    except OSError as exc:
        # Unwritable /data: a fresh id every start would burn a licence seat per
        # restart, so say so loudly. Detection is unaffected.
        logger.warning(f"could not save installation id: {exc}")
    return value


def verify(entitlement: dict | None, this_install: str) -> dict | None:
    """The signed entitlement's contents, or None if it is missing, forged,
    issued to a different installation, or expired."""
    if not entitlement:
        return None
    try:
        payload = base64.b64decode(entitlement["payload"])
        signature = base64.b64decode(entitlement["signature"])
        Ed25519PublicKey.from_public_bytes(base64.b64decode(LICENCE_PUBLIC_KEY)).verify(signature, payload)
        claims = json.loads(payload)
    except (InvalidSignature, KeyError, TypeError, ValueError):
        return None
    if claims.get("v") != 1 or claims.get("install_id") != this_install:
        return None
    if claims.get("exp", 0) <= time.time():
        return None
    return claims


def _granted(claims: dict, reason: str) -> dict:
    return {"valid": True, "plan": claims.get("plan", "licensed"),
            "max_cameras": claims.get("max_cameras"), "reason": reason}


def _read_cache() -> dict | None:
    try:
        with open(CACHE_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(payload: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = CACHE_PATH + ".part"
        with open(tmp, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, CACHE_PATH)
    except OSError as exc:
        # A read-only /data costs a network call per restart, nothing more.
        logger.warning(f"could not cache licence result: {exc}")


def _check_cloud(key: str, this_install: str, addon_version: str | None) -> dict | None:
    """Ask the cloud. Returns None if it could not be reached."""
    try:
        r = httpx.post(f"{CLOUD_URL}/licence/validate",
                       json={"licence_key": key, "install_id": this_install,
                             "addon_version": addon_version}, timeout=10.0)
        if r.status_code != 200:
            logger.warning(f"licence check returned HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as exc:
        logger.info(f"licence server unreachable ({exc.__class__.__name__}) — "
                    f"using cached entitlement if there is one")
        return None


def resolve(licence_key: str, addon_version: str | None = None) -> dict:
    """Decide what this install is entitled to.

    Returns a dict with `valid`, `plan`, `max_cameras` (None = unlimited) and a
    human `reason`. Never raises: any failure resolves to the free tier.
    A paid answer is only ever believed if its signature verifies.
    """
    key = (licence_key or "").strip()
    if not key:
        return _free("no licence key configured")

    this_install = install_id()
    cache = _read_cache()
    cached_claims = None
    if cache and cache.get("key") == key:
        cached_claims = verify(cache.get("entitlement"), this_install)

    fresh_enough = (
        cache
        and cache.get("key") == key
        and (time.time() - cache.get("checked_at", 0)) < REFRESH_SECONDS
    )
    if fresh_enough:
        if cached_claims:
            return _granted(cached_claims, cache.get("reason") or "licence OK")
        if not cache.get("valid"):
            return _free(cache.get("reason") or "licence not valid")
        # Says valid but the signature does not hold up: ask the cloud again.

    result = _check_cloud(key, this_install, addon_version)

    if result is None:
        # Cloud unreachable. Keep honouring a signed answer for this key until
        # it expires, rather than punishing a customer for our downtime or
        # their firewall.
        if cached_claims:
            days = int((time.time() - cached_claims.get("iat", time.time())) // 86400)
            logger.warning(f"using cached licence ({days}d old) — cloud unreachable")
            return _granted(cached_claims, f"cached, cloud unreachable ({days}d old)")
        return _free("cloud unreachable and no valid cached licence")

    if result.get("valid"):
        claims = verify(result.get("entitlement"), this_install)
        if not claims:
            logger.warning("licence answer did not carry a valid signature — free tier")
            return _free("licence answer could not be verified")
        answer = _granted(claims, result.get("reason") or "licence OK")
    else:
        # A definite "no" from the cloud is still cached, so a lapsed customer
        # does not generate a call on every restart.
        answer = _free(result.get("reason") or "licence not valid")

    _write_cache({**answer, "key": key, "checked_at": time.time(),
                  "entitlement": result.get("entitlement")})
    return answer


def describe(entitlement: dict) -> str:
    """One line for the add-on log, which is where a customer looks first."""
    limit = entitlement.get("max_cameras")
    if entitlement.get("valid"):
        plan = entitlement.get("plan", "licensed")
        return f"licence OK ({plan}) — cameras: {'unlimited' if limit is None else limit}"
    return (f"FREE TIER — watching up to {limit} camera(s). "
            f"({entitlement.get('reason')}). "
            f"Add a licence key in the Configuration tab to watch them all.")
