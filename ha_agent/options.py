"""Add-on options, read from the file the Supervisor writes.

Unlike the site agent (edge/config.py) there are no environment variables here:
a Home Assistant add-on is configured entirely from its Configuration tab, and
the Supervisor renders that to /data/options.json.
"""
import json
import os

ADDON_VERSION = "1.5.0"

# The model this release ships — must match model_url/model_sha256 in
# addon/firemex-local/config.yaml (a test checks it).
RELEASES = "https://github.com/malika1234m/Firemax/releases/download"
CURRENT_MODEL = (f"{RELEASES}/model-v4/fire_model.pt",
                 "c29a62d0a76735165da5bc44b4a2c1737c33eb8191898aa8f533b5dbdf321396")

# Models earlier releases shipped. The Supervisor keeps saved options across
# updates, so anyone who once pressed Save on the Configuration tab has the old
# model's address stored and would never get a new model. An address that is
# one of OUR old releases was a default, not a choice: move it to the current
# model. A model_url pointing anywhere else is the user's own and is kept.
SHIPPED_MODEL_URLS = {
    f"{RELEASES}/v0.1.0/fire_model.pt",
    f"{RELEASES}/model-v2/fire_model.pt",
    f"{RELEASES}/model-v3/fire_model.pt",
}

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
    # Licence key from the FiremeX dashboard. Blank is a supported state, not a
    # broken one: an add-on with no key watches one camera so that anyone can
    # try FiremeX on their own footage before paying for anything.
    "licence_key": "",
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
    # Pictures checked per second across ALL cameras together. Every camera
    # shares the one model, so on a Raspberry Pi (about 3 checks a second) 20
    # cameras at process_fps 2 would queue behind each other and fall minutes
    # behind without anyone noticing. Each camera gets min(process_fps,
    # max_total_fps / cameras): with 1–2 cameras nothing changes, with 20 each
    # is checked every 5 seconds — slower, but every camera stays current.
    "max_total_fps": 4.0,
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
    # EZVIZ cameras with Video Encryption ON. Home Assistant cannot show these
    # at all, so the add-on plays them with EZVIZ's own player (ezviz_bridge/),
    # using the owner's EZVIZ Open Platform keys and each camera's verification
    # code, and adds each one to Home Assistant as an MJPEG camera — which
    # FiremeX then watches like any other. Empty list = feature off.
    "ezviz_app_key": "",
    "ezviz_app_secret": "",
    "ezviz_cameras": [],
    "ezviz_fps": 2.0,
    # Only needed to add an EZVIZ camera to Home Assistant by hand.
    "ezviz_bridge_password": "",
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

    if values["model_url"] in SHIPPED_MODEL_URLS:
        values["model_url"], values["model_sha256"] = CURRENT_MODEL

    values["model_path"] = MODEL_PATH
    values["snapshot_dir"] = SNAPSHOT_DIR
    values["ha_config_dir"] = HA_CONFIG_DIR
    return Options(values)
