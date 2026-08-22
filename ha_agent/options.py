"""Add-on options, read from the file the Supervisor writes.

Unlike the site agent (edge/config.py) there are no environment variables here:
a Home Assistant add-on is configured entirely from its Configuration tab, and
the Supervisor renders that to /data/options.json.
"""
import json
import os

ADDON_VERSION = "1.1.0"

OPTIONS_PATH = os.environ.get("OPTIONS_PATH", "/data/options.json")

# /data survives restarts and add-on updates, so weights are downloaded once.
MODEL_PATH = os.environ.get("MODEL_PATH", "/data/fire_model.pt")

# Where annotated alert snapshots are written. Inside the add-on this is Home
# Assistant's own www/ directory (granted by `map: homeassistant_config:rw`),
# which HA serves at /local/ — so the dashboard can show the evidence frame
# with no extra web server and nothing exposed off the machine.
SNAPSHOT_DIR = os.environ.get("SNAPSHOT_DIR", "/homeassistant/www/firemex")

# How HOME ASSISTANT sees its own config directory. The add-on sees that same
# directory at /homeassistant (via `map: homeassistant_config:rw`), but a path
# handed to a local_file camera is resolved by Home Assistant, not by us, so
# the two must not be confused.
HA_CONFIG_DIR = os.environ.get("HA_CONFIG_DIR", "/config")

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
    # A camera that stops delivering frames raises its own alert. The grace
    # period stops every restart alerting, since a camera has legitimately
    # delivered nothing yet at startup.
    "camera_offline_after_seconds": 60,
    # Keep the annotated evidence frame for each alert. This is what an
    # operator actually judges a true or false alarm on — a bare "fire 88%" is
    # not something a human can confirm or reject.
    "save_snapshots": True,
    # Which hazard classes may raise an alert.
    #
    # Defaults to the LEARNED classes only. The deterministic colour and
    # optical-flow branches are the project's distinctive contribution, but
    # they misfire badly on frames that have been through Home Assistant's
    # camera proxy: the proxy re-encodes every frame, and that compression
    # noise reads as heat shimmer, while blue sky and pale smoke read as a gas
    # flame. In testing they fired continuously at 82-95% on ordinary footage.
    #
    # An operator console that cries wolf is worse than one with fewer
    # features — people stop reading it, and then the real alert is missed too.
    # Add "gas_fire", "lpg_fire", "chemical_fire", "gas_shimmer" or
    # "person_down" here once you have tested them against your own cameras.
    "hazard_classes": ["fire", "smoke", "flame"],
    # Create the FiremeX helpers, automations, snapshot cameras and dashboard
    # on start. On by default so installing the add-on and pressing Start is
    # the whole setup — a client should never have to run a script by hand.
    #
    # Provisioning is idempotent and never overwrites a helper that exists, but
    # it DOES rewrite the FiremeX dashboard's views. Turn this off once you
    # have customised them, or your edits go back every restart.
    "provision_dashboard": True,
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
    values["snapshot_dir"] = SNAPSHOT_DIR
    values["ha_config_dir"] = HA_CONFIG_DIR
    return Options(values)
