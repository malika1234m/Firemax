"""Entrypoint used by BOTH delivery routes for the same image.

The agent ships two ways:

  • `docker compose up` on a customer box — configured by environment variables
    (edge/docker-compose.yml + edge.env).
  • a Home Assistant add-on — configured by the user in HA's Configuration tab.

An add-on never receives environment variables. The Supervisor writes whatever
the user typed into `/data/options.json`, so this translates that file into the
environment variables `edge/config.py` already reads and then hands off to the
agent completely unchanged.

Deliberately ONE image for both routes. A second image would be a second thing
to publish from a second workflow, and the two would drift — which in this
product means a site silently running detection logic we thought we'd replaced.

`agent.py` is not modified by any of this: it still reads only environment
variables and knows nothing about Home Assistant.
"""
import json
import os
import sys

# The Supervisor writes the add-on's user configuration here. Its presence is
# what distinguishes "running as a Home Assistant add-on" from "running under
# docker compose" — an ordinary install has no /data at all.
OPTIONS_PATH = "/data/options.json"

# add-on option name -> the environment variable edge/config.py reads.
OPTION_ENV = {
    "cloud_url":            "FIREMEX_CLOUD_URL",
    "agent_token":          "AGENT_TOKEN",
    "detector_mode":        "DETECTOR_MODE",
    "model_url":            "MODEL_URL",
    "model_sha256":         "MODEL_SHA256",
    "heartbeat_interval":   "HEARTBEAT_INTERVAL",
    "config_poll_interval": "CONFIG_POLL_INTERVAL",
}

# /data is the add-on's persistent volume: it survives restarts AND add-on
# updates. The image default (models/fire_model.pt) lives in the container
# layer, so every update would re-download ~6 MB of weights and, worse, a site
# would sit undefended while it did.
ADDON_MODEL_PATH = "/data/fire_model.pt"


def apply_addon_options(path: str = OPTIONS_PATH) -> bool:
    """Populate os.environ from the add-on options file. Returns True if this
    process is running as a Home Assistant add-on."""
    if not os.path.exists(path):
        return False

    with open(path) as fh:
        options = json.load(fh)

    for key, env_var in OPTION_ENV.items():
        value = options.get(key)
        # A blank optional field comes through as "" — leaving it unset lets
        # edge/config.py apply its own default rather than overriding it with
        # an empty string, which is not the same thing (MODEL_URL="" means
        # "never download", MODEL_URL unset means the same, but HEARTBEAT_
        # INTERVAL="" would crash int()).
        if value is None or value == "":
            continue
        os.environ[env_var] = str(value)

    os.environ["MODEL_PATH"] = ADDON_MODEL_PATH
    return True


def main():
    # Passed explicitly rather than relying on the default argument, which is
    # bound once at import and cannot be pointed elsewhere by a test.
    as_addon = apply_addon_options(OPTIONS_PATH)

    # config.py reads the environment at import time (its values are class
    # attributes evaluated on first import), so the environment MUST be fully
    # populated before agent is imported. Importing at module scope above
    # would capture the environment before the options file was read.
    from config import AGENT_VERSION

    if as_addon:
        print(f"[ha] FiremeX add-on v{AGENT_VERSION} — configuration read from {OPTIONS_PATH}")
        print(f"[ha] cloud={os.environ.get('FIREMEX_CLOUD_URL')}  "
              f"detector={os.environ.get('DETECTOR_MODE')}  model={ADDON_MODEL_PATH}")
        if not os.environ.get("AGENT_TOKEN"):
            # Fail with the actual next step rather than a stack trace. This is
            # the mistake every first-time installer makes.
            raise SystemExit(
                "No enrollment token set.\n"
                "  Open FiremeX -> Sites -> Create Site, copy the token, then paste it\n"
                "  into this add-on's Configuration tab as 'agent_token' and restart."
            )
    else:
        print(f"[ha] No {OPTIONS_PATH} — running from environment variables.")

    import agent
    agent.run()


if __name__ == "__main__":
    sys.exit(main())
