"""The add-on side of EZVIZ support.

    backend/.venv/bin/python -m pytest ha_agent/tests -q      (from the repo root)
"""
import json
import logging
import os
import stat
import sys
import threading
import time

import pytest

from ha_agent import ezviz, options

CAMS = [{"name": "Front Door", "serial": "BC1234567", "verify_code": "ABCDEF"}]


def run(command, stop_after=3.0):
    stop = threading.Event()
    bridge = ezviz.Bridge(stop, command=command, env=dict(os.environ)).start()
    time.sleep(stop_after)
    stop.set()
    bridge.stop()
    return bridge


@pytest.fixture
def auth_path(tmp_path, monkeypatch):
    path = tmp_path / "ezviz_bridge_auth.json"
    monkeypatch.setattr(ezviz, "AUTH_PATH", str(path))
    return path


# ── isolation: the browser side gets only what it needs ──────────────────────
def test_bridge_never_gets_the_home_assistant_token():
    base = {"SUPERVISOR_TOKEN": "HA-TOKEN-VALUE-1", "HASSIO_TOKEN": "HA-TOKEN-VALUE-2", "PATH": "/usr/bin",
            "CHROME_PATH": "/usr/bin/chromium", "SOMETHING_ELSE": "x"}
    env = ezviz.bridge_env(options.Options(ezviz_app_key="k", ezviz_app_secret="s", ezviz_cameras=CAMS),
                           {"username": "firemex", "password": "p" * 32}, base)
    assert "SUPERVISOR_TOKEN" not in env and "HASSIO_TOKEN" not in env
    assert "HA-TOKEN-VALUE" not in json.dumps(env)
    assert "SOMETHING_ELSE" not in env
    assert env["CHROME_PATH"] == "/usr/bin/chromium"
    cfg = json.loads(env["BRIDGE_CONFIG_JSON"])
    assert cfg["app_key"] == "k" and cfg["cameras"] == CAMS
    assert env["HOME"] == ezviz.BRIDGE_HOME                       # writable temp home only


def test_not_root_means_no_user_switch(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    assert ezviz._demote() == {}


def test_bridge_credentials_are_private_and_kept(auth_path):
    a = ezviz.load_auth()
    assert len(a["password"]) >= 24
    assert stat.S_IMODE(os.stat(auth_path).st_mode) == 0o600
    assert ezviz.load_auth() == a                                  # same after a restart
    chosen = ezviz.load_auth("my-own-password-123")
    assert chosen["password"] == "my-own-password-123"
    assert "my-own-password-123" not in auth_path.read_text()     # never written


# ── supervising the process ──────────────────────────────────────────────────
def test_off_unless_ezviz_cameras_are_configured():
    assert ezviz.wanted(options.Options(ezviz_cameras=[])) is False
    assert ezviz.wanted(options.Options(options.DEFAULTS)) is False
    assert ezviz.wanted(options.Options(ezviz_cameras=CAMS)) is True


def test_bridge_output_reaches_the_addon_log(caplog):
    caplog.set_level(logging.INFO, logger="ezviz")
    run([sys.executable, "-u", "-c", "print('2026-10-18T00:00:00Z Gate: playing — frames flowing'); "
                                     "import time; time.sleep(5)"], stop_after=1.5)
    assert "Gate: playing — frames flowing" in caplog.text
    assert "2026-10-18T00:00:00Z" not in caplog.text


def test_settings_error_is_reported_once_not_retried(caplog):
    caplog.set_level(logging.INFO, logger="ezviz")
    run([sys.executable, "-u", "-c", "print('EZVIZ cameras are not set up: ezviz_app_key is empty'); "
                                     "raise SystemExit(2)"], stop_after=1.5)
    assert caplog.text.count("ezviz_app_key is empty") == 1
    assert "Fix the ezviz_ options" in caplog.text
    assert "restarting" not in caplog.text


def test_crash_is_restarted(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="ezviz")
    real_wait = threading.Event.wait
    monkeypatch.setattr(threading.Event, "wait", lambda self, t=None: real_wait(self, 0.05 if t else t))
    run([sys.executable, "-u", "-c", "print('started'); raise SystemExit(1)"], stop_after=1.0)
    assert caplog.text.count("started") >= 2
    assert "restarting" in caplog.text


# ── adding cameras to Home Assistant ─────────────────────────────────────────
class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHA:
    base_url = "http://supervisor/core/api"

    def __init__(self, existing=(), fail=False):
        self.calls, self._existing, self._fail = [], list(existing), fail
        self._client = self

    def get(self, url, **kw):
        self.calls.append(("GET", url, None))
        return FakeResponse(self._existing)

    def post(self, url, json=None, **kw):
        self.calls.append(("POST", url, json))
        if self._fail:
            return FakeResponse({}, 500)
        if url.endswith("/flow"):
            return FakeResponse({"flow_id": "f1"})
        return FakeResponse({"type": "create_entry"})


AUTH = {"username": "firemex", "password": "p" * 32}


def test_camera_is_added_through_the_mjpeg_flow_with_the_bridge_credentials():
    ha = FakeHA()
    assert ezviz.register_camera(ha, "Front Door", AUTH, host="bd0c1f44-firemex-local") == "added to Home Assistant"
    start = [c for c in ha.calls if c[1].endswith("/flow")][0][2]
    submit = [c for c in ha.calls if c[1].endswith("/flow/f1")][0][2]
    assert start["handler"] == "mjpeg"
    assert submit["mjpeg_url"] == "http://bd0c1f44-firemex-local:8095/front_door/stream.mjpg"
    assert submit["still_image_url"] == "http://bd0c1f44-firemex-local:8095/front_door/snapshot.jpg"
    assert (submit["username"], submit["password"]) == (AUTH["username"], AUTH["password"])


def test_camera_already_in_home_assistant_is_not_added_twice():
    ha = FakeHA(existing=[{"domain": "mjpeg", "title": "Front Door"}])
    assert ezviz.register_camera(ha, "Front Door", AUTH) == "already in Home Assistant"
    assert [c[0] for c in ha.calls] == ["GET"]


def test_registered_only_once_playing_and_failure_never_logs_the_password(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="ezviz")
    states = iter([[{"name": "Front Door", "state": "starting"}],
                   [{"name": "Front Door", "state": "playing"}]])
    monkeypatch.setattr(ezviz.httpx, "get", lambda *a, **k: FakeResponse(next(states)))
    bridge = ezviz.Bridge(threading.Event(), options.Options(ezviz_cameras=CAMS), command=["true"], env={})
    bridge.auth = AUTH
    stop = threading.Event()
    real_wait = threading.Event.wait
    monkeypatch.setattr(threading.Event, "wait", lambda self, t=None: real_wait(self, 0.01 if t else t))
    ha = FakeHA(fail=True)
    ezviz.register_when_playing(ha, bridge, stop)
    posts = [c for c in ha.calls if c[0] == "POST"]
    assert posts, "registration was attempted once the camera played"
    assert "add it by hand" in caplog.text
    assert AUTH["password"] not in caplog.text


# ── the browser's home cannot be used to take over another directory ────────
def _as_root(monkeypatch, tmp_path):
    import pwd
    me = pwd.getpwuid(os.getuid())
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(ezviz.pwd, "getpwnam", lambda name: me)
    chowned = []
    monkeypatch.setattr(os, "chown", lambda path, uid, gid, follow_symlinks=True: chowned.append((path, follow_symlinks)))
    real_lstat = os.lstat

    class RootOwned:
        def __init__(self, st):
            self.st_mode, self.st_uid = st.st_mode, 0

    monkeypatch.setattr(os, "lstat", lambda p: RootOwned(real_lstat(p)))
    return chowned


def test_each_start_gets_a_fresh_home_and_symlinks_are_not_followed(monkeypatch, tmp_path):
    parent = tmp_path / "run-ezviz"
    monkeypatch.setattr(ezviz, "BRIDGE_HOME_PARENT", str(parent))
    chowned = _as_root(monkeypatch, tmp_path)
    a, b = ezviz._demote(), ezviz._demote()
    assert a["cwd"] != b["cwd"]                                   # never re-used
    assert all(p.startswith(str(parent)) for p in (a["cwd"], b["cwd"]))
    assert chowned and all(follow is False for _, follow in chowned)


def test_a_writable_or_foreign_parent_is_refused(monkeypatch, tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir()
    os.chmod(parent, 0o777)                                       # anyone could swap things in it
    monkeypatch.setattr(ezviz, "BRIDGE_HOME_PARENT", str(parent))
    _as_root(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="root-owned"):
        ezviz._demote()
