"""Edge-agent configuration, all from environment variables.

The agent runs on the customer's own network. It only ever dials OUT to the
FiremeX cloud, authenticating with the site enrollment token generated in the
FiremeX app (Sites page).
"""
import os

AGENT_VERSION = "0.2.0"


class AgentConfig:
    # Where the FiremeX cloud control plane lives.
    cloud_url = os.environ.get("FIREMEX_CLOUD_URL", "http://localhost:8000").rstrip("/")
    # The site enrollment token (Sites → Create Site → shown once).
    token = os.environ.get("AGENT_TOKEN", "")
    # Seconds between heartbeats to the cloud.
    heartbeat_interval = int(os.environ.get("HEARTBEAT_INTERVAL", "10"))
    # Seconds between re-reading the camera list and detection tuning. Without
    # this the agent only ever saw the configuration it started with, so adding,
    # disabling or deleting a camera in the app required a container restart.
    config_poll_interval = int(os.environ.get("CONFIG_POLL_INTERVAL", "30"))
    # "yolo" runs the real detection model; "mock" runs without any ML deps
    # (useful for wiring/tests and low-power boxes during setup).
    detector_mode = os.environ.get("DETECTOR_MODE", "yolo").lower()
    # Path to the YOLO model when detector_mode == "yolo".
    model_path = os.environ.get("MODEL_PATH", "models/fire_model.pt")
    # Weights are distributed out-of-band (too large for the agent image). If
    # the file is missing and this is set, the agent downloads it on first run
    # and caches it at model_path — so a customer never has to copy a .pt by
    # hand. MODEL_SHA256 pins the file; strongly recommended.
    model_url = os.environ.get("MODEL_URL", "")
    model_sha256 = os.environ.get("MODEL_SHA256", "")

    # For local testing with a laptop webcam: set WEBCAM_CAMERA_ID to an
    # existing camera's id, and the agent will feed that camera from the local
    # webcam device (WEBCAM_DEVICE, default 0) instead of its configured URL.
    webcam_camera_id = os.environ.get("WEBCAM_CAMERA_ID", "")
    webcam_device = int(os.environ.get("WEBCAM_DEVICE", "0"))

    @classmethod
    def require_token(cls):
        if not cls.token:
            raise SystemExit("AGENT_TOKEN is not set. Create a Site in FiremeX and paste its enrollment token.")
