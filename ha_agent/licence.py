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

The cache is not tamper-proof and is not meant to be: it is a plain JSON file on
the customer's own machine. Anyone determined to edit it can, and would also
have been able to fork the add-on. This exists to make paying the easy path, not
to fight the owner of the hardware.
"""
import json
import logging
import os
import time

import httpx

logger = logging.getLogger("ha.licence")

# The public API. Overridable so the add-on can be pointed at a staging cloud
# during development without editing the image.
CLOUD_URL = os.environ.get("FIREMEX_CLOUD_URL",
                           "https://firemex-backend.up.railway.app").rstrip("/")

CACHE_PATH = os.environ.get("LICENCE_CACHE_PATH", "/data/licence.json")

# How often a licence is re-checked when the cloud is reachable.
REFRESH_SECONDS = 7 * 24 * 3600

# How long a cached "valid" answer keeps working while the cloud is unreachable.
# Generous on purpose: a site with a flaky uplink, or one deliberately kept off
# the internet after setup, must not silently lose cameras. After this the
# add-on drops to the free tier — it never stops.
OFFLINE_GRACE_SECONDS = 60 * 24 * 3600

FREE_TIER_MAX_CAMERAS = 1


def _free(reason: str) -> dict:
    return {"valid": False, "plan": "free",
            "max_cameras": FREE_TIER_MAX_CAMERAS, "reason": reason}


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


def _check_cloud(key: str) -> dict | None:
    """Ask the cloud. Returns None if it could not be reached."""
    try:
        r = httpx.post(f"{CLOUD_URL}/licence/validate",
                       json={"licence_key": key}, timeout=10.0)
        if r.status_code != 200:
            logger.warning(f"licence check returned HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as exc:
        logger.info(f"licence server unreachable ({exc.__class__.__name__}) — "
                    f"using cached entitlement if there is one")
        return None


def resolve(licence_key: str) -> dict:
    """Decide what this install is entitled to.

    Returns a dict with `valid`, `plan`, `max_cameras` (None = unlimited) and a
    human `reason`. Never raises: any failure resolves to the free tier.
    """
    key = (licence_key or "").strip()
    if not key:
        return _free("no licence key configured")

    cache = _read_cache()
    fresh_enough = (
        cache
        and cache.get("key") == key
        and (time.time() - cache.get("checked_at", 0)) < REFRESH_SECONDS
    )
    if fresh_enough:
        return {k: cache[k] for k in ("valid", "plan", "max_cameras", "reason")
                if k in cache}

    result = _check_cloud(key)

    if result is None:
        # Cloud unreachable. Keep honouring a cached answer for this same key
        # rather than punishing a customer for our downtime or their firewall.
        if cache and cache.get("key") == key:
            age = time.time() - cache.get("checked_at", 0)
            if age < OFFLINE_GRACE_SECONDS and cache.get("valid"):
                days = int(age // 86400)
                logger.warning(f"using cached licence ({days}d old) — cloud unreachable")
                return {"valid": True, "plan": cache.get("plan", "unknown"),
                        "max_cameras": cache.get("max_cameras"),
                        "reason": f"cached, cloud unreachable ({days}d old)"}
            return _free("cached licence too old and cloud unreachable")
        return _free("cloud unreachable and no cached licence")

    result.setdefault("max_cameras", FREE_TIER_MAX_CAMERAS)
    if not result.get("valid"):
        # A definite "no" from the cloud is still cached, so a lapsed customer
        # does not generate a call on every restart.
        result["max_cameras"] = result.get("max_cameras") or FREE_TIER_MAX_CAMERAS

    _write_cache({**result, "key": key, "checked_at": time.time()})
    return result


def describe(entitlement: dict) -> str:
    """One line for the add-on log, which is where a customer looks first."""
    limit = entitlement.get("max_cameras")
    if entitlement.get("valid"):
        plan = entitlement.get("plan", "licensed")
        return f"licence OK ({plan}) — cameras: {'unlimited' if limit is None else limit}"
    return (f"FREE TIER — watching up to {limit} camera(s). "
            f"({entitlement.get('reason')}). "
            f"Add a licence key in the Configuration tab to watch them all.")
