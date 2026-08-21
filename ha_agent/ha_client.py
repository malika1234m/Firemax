"""Home Assistant Core API client for the fully-local FiremeX add-on.

An add-on declaring `homeassistant_api: true` is handed a SUPERVISOR_TOKEN and
reaches Core through the Supervisor's proxy at http://supervisor/core/api. That
means no URL, no port and no long-lived token for the user to configure — and
nothing ever leaves the machine.

This is the ONLY thing the local add-on talks to. There is no FiremeX cloud in
this deployment: cameras come from Home Assistant, and hazards go back to Home
Assistant.
"""
import logging
import os

import httpx

logger = logging.getLogger("ha.client")

# The Supervisor proxies this to Core. Overridable so the agent can be pointed
# at a plain Home Assistant instance for development outside an add-on.
DEFAULT_API = "http://supervisor/core/api"

# Kept identical to the cloud's app/config.py HA_WEBHOOK_ID and to the sensor
# name in app/services/notifications.py. An automation written against cloud
# FiremeX therefore works unchanged against this add-on — the payloads and the
# entity are the same, only the sender is local.
HAZARD_SENSOR = "sensor.firemex_hazard"
HAZARD_WEBHOOK = "firemax_hazard_alert"
CLEAR_WEBHOOK = "firemax_hazard_clear"
HAZARD_EVENT = "firemex_hazard"


class HAClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or os.environ.get("HA_API_URL") or DEFAULT_API).rstrip("/")
        self.token = token if token is not None else os.environ.get("SUPERVISOR_TOKEN", "")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, headers=self.headers)

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # ── discovery ──────────────────────────────────────────────────────────
    def list_cameras(self) -> list[dict]:
        """Every camera entity Home Assistant knows about.

        This is the point of the design: FiremeX never learns about a camera
        from its own configuration, and never opens one itself. Whatever
        integration provides the camera — Hikvision, ONVIF, generic RTSP — has
        already done the work of connecting to it, and FiremeX reads the result.
        """
        r = self._client.get(f"{self.base_url}/states")
        r.raise_for_status()
        cameras = []
        for state in r.json():
            entity_id = state.get("entity_id", "")
            if not entity_id.startswith("camera."):
                continue
            # An unavailable camera is one HA cannot currently reach. Watching
            # it would just spin a reader against nothing.
            if state.get("state") in ("unavailable", "unknown"):
                logger.info(f"skipping {entity_id} (state={state.get('state')})")
                continue
            attrs = state.get("attributes", {})
            cameras.append({
                "entity_id": entity_id,
                "name": attrs.get("friendly_name") or entity_id.split(".", 1)[1],
            })
        return cameras

    def camera_stream_url(self, entity_id: str) -> str:
        """MJPEG proxy for a camera entity. Home Assistant holds the actual
        camera connection; this is a re-encoded view of it."""
        return f"{self.base_url}/camera_proxy_stream/{entity_id}"

    def open_stream(self, entity_id: str):
        """Context manager yielding a streaming MJPEG response."""
        return self._client.stream("GET", self.camera_stream_url(entity_id), timeout=None)

    # ── publishing hazards back to Home Assistant ──────────────────────────
    def publish_hazard(self, hazard_type: str, camera_name: str, confidence: float,
                       entity_id: str, timestamp: str) -> None:
        """Announce a hazard three ways, because Home Assistant users trigger
        automations three different ways and we do not get to choose for them:

          1. an event      — the idiomatic automation trigger
          2. a sensor      — so it is visible on a dashboard and has history
          3. the webhook   — so ha_automation.yaml in this repo, written for
                             cloud FiremeX, keeps working with no edits
        """
        payload = {
            "hazard_type": hazard_type,
            "camera_name": camera_name,
            "confidence": confidence,
            "entity_id": entity_id,
            "timestamp": timestamp,
        }
        self._post(f"/events/{HAZARD_EVENT}", payload, "event")
        self._post(f"/states/{HAZARD_SENSOR}", {
            "state": hazard_type,
            "attributes": {
                "friendly_name": "FiremeX Hazard",
                "icon": "mdi:fire-alert",
                "hazard_type": hazard_type,
                "camera_name": camera_name,
                "entity_id": entity_id,
                "confidence": f"{confidence:.0%}",
                "confidence_raw": confidence,
                "timestamp": timestamp,
            },
        }, "sensor")
        self._post(f"/webhook/{HAZARD_WEBHOOK}", payload, "webhook")

    def publish_clear(self, timestamp: str) -> None:
        """Return the sensor to 'clear' once nothing has been seen for a while.

        The cloud never did this — an alert there is a record, not a state. A
        Home Assistant sensor IS a state, so leaving it stuck on "fire" forever
        would make every dashboard and template condition wrong.
        """
        self._post(f"/states/{HAZARD_SENSOR}", {
            "state": "clear",
            "attributes": {
                "friendly_name": "FiremeX Hazard",
                "icon": "mdi:fire-off",
                "timestamp": timestamp,
            },
        }, "sensor")
        self._post(f"/webhook/{CLEAR_WEBHOOK}", {"timestamp": timestamp}, "webhook")

    def _post(self, path: str, payload: dict, what: str) -> None:
        # One failing channel must never stop the others — a broken webhook
        # should not also cost you the sensor update.
        try:
            r = self._client.post(f"{self.base_url}{path}", json=payload)
            # A webhook with no automation listening returns 200 with no effect;
            # 404 means the webhook id genuinely does not exist, which is normal
            # if the user never imported ha_automation.yaml.
            if r.status_code == 404 and "/webhook/" in path:
                return
            r.raise_for_status()
        except Exception as exc:
            logger.warning(f"could not publish {what} ({path}): {exc}")

    def ping(self) -> bool:
        try:
            r = self._client.get(f"{self.base_url}/")
            r.raise_for_status()
            return True
        except Exception as exc:
            logger.error(f"cannot reach Home Assistant at {self.base_url}: {exc}")
            return False

    def close(self):
        self._client.close()
