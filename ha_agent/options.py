"""Add-on options, read from the file the Supervisor writes.

Unlike the site agent (edge/config.py) there are no environment variables here:
a Home Assistant add-on is configured entirely from its Configuration tab, and
the Supervisor renders that to /data/options.json.
"""
import json
import os

ADDON_VERSION = "1.0.0"

OPTIONS_PATH = os.environ.get("OPTIONS_PATH", "/data/options.json")

# /data survives restarts and add-on updates, so weights are downloaded once.
MODEL_PATH = os.environ.get("MODEL_PATH", "/data/fire_model.pt")

DEFAULTS = {
    # Empty means "every camera entity Home Assistant has". Naming entities
    # explicitly is how a user limits detection to the cameras that matter —
    # running the model on a doorbell adds cost and false alarms, not safety.
    "cameras": [],
    "confidence_threshold": 0.50,
    "alert_cooldown_seconds": 30,
    "detector_mode": "yolo",
    "model_url": "",
    "model_sha256": "",
    # Detection rate per camera. Home Assistant's MJPEG proxy re-encodes, so
    # this is deliberately far below the site agent's 5 fps: a Pi running HA is
    # doing many other things, and fire does not appear and vanish in 500ms.
    "process_fps": 2.0,
    # Seconds of quiet before the sensor returns to "clear".
    "clear_after_seconds": 120,
}


class Options(dict):
    """Options with defaults applied, readable as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def load(path: str | None = None) -> Options:
    path = path or OPTIONS_PATH
    values = dict(DEFAULTS)

    if os.path.exists(path):
        with open(path) as fh:
            user = json.load(fh)
        for key, default in DEFAULTS.items():
            value = user.get(key)
            # A cleared optional field arrives as "" — that is not the same as
            # the user choosing an empty value, so fall back to the default.
            if value is None or value == "":
                continue
            values[key] = value

    values["model_path"] = MODEL_PATH
    return Options(values)
