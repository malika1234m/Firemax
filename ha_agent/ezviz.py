"""Runs the EZVIZ bridge (ezviz_bridge/bridge.mjs) inside the FiremeX add-on.

EZVIZ cameras with Video Encryption ON only play in EZVIZ's own player. The
bridge runs that official player in headless Chromium, with the owner's EZVIZ
Open Platform keys and each camera's verification code, and serves the decoded
pictures as MJPEG. This module then adds each camera to Home Assistant, where
FiremeX's ordinary camera discovery finds it.

The browser plays content from the internet, so it is kept away from anything
valuable. It runs as the unprivileged `ezviz` user, gets only its EZVIZ
settings and its own HTTP credentials through the environment — never
SUPERVISOR_TOKEN, never /data — and can write only to its own temporary home.
Registering cameras with Home Assistant, which needs the Supervisor token,
happens here in the main process instead.
"""
import json
import logging
import os
import pwd
import secrets
import socket
import subprocess
import threading
import time

import httpx

logger = logging.getLogger("ezviz")

BRIDGE = os.environ.get("EZVIZ_BRIDGE", "/app/ezviz_bridge/bridge.mjs")
PORT = int(os.environ.get("EZVIZ_BRIDGE_PORT", "8095"))
AUTH_PATH = os.environ.get("EZVIZ_AUTH_PATH", "/data/ezviz_bridge_auth.json")
RUN_AS = os.environ.get("EZVIZ_RUN_AS", "ezviz")
BRIDGE_HOME = os.environ.get("EZVIZ_HOME", "/tmp/ezviz")

# bridge.mjs exits with this when its settings are wrong. Restarting cannot fix
# that, so the add-on says so and waits for the owner to change the settings.
CONFIG_ERROR = 2

# Only these reach the bridge's environment. Everything else — above all
# SUPERVISOR_TOKEN — stays in the main process.
PASS_THROUGH = ("PATH", "CHROME_PATH", "PUPPETEER_SKIP_DOWNLOAD", "PUPPETEER_PATH", "NODE_ENV",
                "LANG", "TZ", "BRIDGE_FAKE", "BRIDGE_DEBUG")


def wanted(options) -> bool:
    return bool(options.get("ezviz_cameras"))


def slugify(name: str) -> str:
    """Same rule as ezviz_bridge/config.mjs — the URL path and camera.<slug>."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", str(name).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "camera"


def load_auth(chosen: str = "") -> dict:
    """The bridge's HTTP credentials, created once and kept (0600, root) in
    /data so the camera Home Assistant saved keeps working across restarts. An
    owner-chosen ezviz_bridge_password wins; it is never written or logged."""
    if chosen:
        return {"username": "firemex", "password": chosen}
    try:
        with open(AUTH_PATH) as fh:
            auth = json.load(fh)
        if auth.get("username") and len(auth.get("password", "")) >= 24:
            return auth
    except (OSError, ValueError):
        pass
    auth = {"username": "firemex", "password": secrets.token_urlsafe(24)}
    try:
        fd = os.open(AUTH_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(auth, fh)
    except OSError as exc:
        logger.warning(f"could not save bridge credentials ({exc}); a new set is made each start")
    return auth


def bridge_env(options, auth: dict, base_env=None) -> dict:
    base = os.environ if base_env is None else base_env
    env = {k: base[k] for k in PASS_THROUGH if k in base}
    env.update({
        "HOME": BRIDGE_HOME,
        "BRIDGE_PORT": str(PORT),
        "BRIDGE_USERNAME": auth["username"],
        "BRIDGE_PASSWORD": auth["password"],
        "BRIDGE_CONFIG_JSON": json.dumps({
            "app_key": options.get("ezviz_app_key", ""),
            "app_secret": options.get("ezviz_app_secret", ""),
            "api": options.get("ezviz_api", ""),
            "cameras": options.get("ezviz_cameras", []),
            "fps": options.get("ezviz_fps", 2),
            "bridge_password": options.get("ezviz_bridge_password", ""),
        }),
    })
    return env


def _demote():
    """Popen arguments that run the bridge as the unprivileged user — when we
    are root and that user exists (the add-on image). On a development machine
    it runs as whoever started it."""
    if os.geteuid() != 0:
        return {}
    try:
        user = pwd.getpwnam(RUN_AS)
    except KeyError:
        logger.warning(f"user {RUN_AS!r} not found — running the EZVIZ bridge as root")
        return {}
    os.makedirs(BRIDGE_HOME, mode=0o700, exist_ok=True)
    os.chown(BRIDGE_HOME, user.pw_uid, user.pw_gid)
    return {"user": user.pw_uid, "group": user.pw_gid, "extra_groups": [], "cwd": BRIDGE_HOME}


class Bridge:
    def __init__(self, stop: threading.Event, options=None, command=None, env=None):
        self._stop = stop
        self._command = command or ["node", BRIDGE]
        self._options = options or {}
        self.auth = load_auth(self._options.get("ezviz_bridge_password", "")) if env is None else None
        self._env = env if env is not None else bridge_env(self._options, self.auth)
        self._proc = None
        self._thread = threading.Thread(target=self._supervise, daemon=True, name="ezviz-bridge")

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _supervise(self):
        backoff = 5
        while not self._stop.is_set():
            started = time.time()
            code = self._run_once()
            if self._stop.is_set():
                return
            if code == CONFIG_ERROR:
                logger.error("EZVIZ cameras are not set up correctly (see the line above). "
                             "Fix the ezviz_ options in the Configuration tab and restart the add-on.")
                return
            if time.time() - started > 600:
                backoff = 5                      # it had been working; retry quickly
            logger.warning(f"EZVIZ bridge stopped (exit {code}); restarting in {backoff}s")
            self._stop.wait(backoff)
            backoff = min(backoff * 2, 300)

    def _run_once(self) -> int:
        try:
            self._proc = subprocess.Popen(
                self._command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=self._env, **_demote())
        except OSError as exc:
            logger.error(f"could not start the EZVIZ bridge: {exc}")
            return 1
        for line in self._proc.stdout:
            line = line.rstrip()
            if line:
                # The bridge prefixes its own ISO timestamp; ours is enough.
                logger.info(line.split(" ", 1)[1] if line[:4].isdigit() and " " in line else line)
        return self._proc.wait()


# ── adding the cameras to Home Assistant (needs the Supervisor token) ─────────
def camera_urls(slug: str, host: str | None = None) -> dict:
    host = host or socket.gethostname()
    return {"mjpeg_url": f"http://{host}:{PORT}/{slug}/stream.mjpg",
            "still_image_url": f"http://{host}:{PORT}/{slug}/snapshot.jpg"}


def register_camera(client, name: str, auth: dict, host: str | None = None) -> str:
    """Add one camera through Home Assistant's own MJPEG config flow — what a
    user would do under Settings > Devices & services. Home Assistant tests the
    address before saving, so call this once the bridge has a picture."""
    api = client.base_url
    http = client._client
    entries = http.get(f"{api}/config/config_entries/entry")
    entries.raise_for_status()
    if any(e.get("domain") == "mjpeg" and e.get("title") == name for e in entries.json()):
        return "already in Home Assistant"
    flow = http.post(f"{api}/config/config_entries/flow",
                     json={"handler": "mjpeg", "show_advanced_options": False})
    flow.raise_for_status()
    result = http.post(f"{api}/config/config_entries/flow/{flow.json()['flow_id']}",
                       json={"name": name, **camera_urls(slugify(name), host),
                             "username": auth["username"], "password": auth["password"],
                             "verify_ssl": False})
    result.raise_for_status()
    body = result.json()
    if body.get("type") == "create_entry":
        return "added to Home Assistant"
    if body.get("type") == "abort" and body.get("reason") == "already_configured":
        return "already in Home Assistant"
    raise RuntimeError(f"Home Assistant refused it: {body.get('errors') or body.get('reason')}")


def register_when_playing(client, bridge: Bridge, stop: threading.Event, status_url=None):
    """Wait for each camera's first picture, then add it to Home Assistant."""
    status_url = status_url or f"http://127.0.0.1:{PORT}/status"
    pending = {c["name"] for c in bridge._options.get("ezviz_cameras", [])}
    deadline = time.time() + 3600
    while pending and not stop.is_set() and time.time() < deadline:
        try:
            r = httpx.get(status_url, auth=(bridge.auth["username"], bridge.auth["password"]), timeout=5)
            playing = {c["name"] for c in r.json() if c.get("state") == "playing"}
        except Exception:
            playing = set()
        for name in sorted(pending & playing):
            pending.discard(name)
            try:
                logger.info(f"{name}: {register_camera(client, name, bridge.auth)} (camera.{slugify(name)})")
            except Exception as exc:
                # Everything needed to add it by hand — except the password,
                # which is never logged: the owner sets ezviz_bridge_password.
                urls = camera_urls(slugify(name))
                logger.warning(f"{name}: could not add to Home Assistant: {exc}")
                logger.warning(f"  add it by hand (MJPEG IP Camera): MJPEG URL {urls['mjpeg_url']}  "
                               f"still image URL {urls['still_image_url']}  username {bridge.auth['username']}"
                               f"  password: set \"ezviz_bridge_password\" in the Configuration tab, "
                               f"restart, and use that")
        stop.wait(5)
    for name in sorted(pending):
        logger.warning(f"{name}: no picture yet, so not added to Home Assistant")
