"""The add-on side of EZVIZ support: start the bridge only when wanted, pass its
log through, never relaunch it for a settings error, and relaunch it after a
crash.

    backend/.venv/bin/python -m pytest ha_agent/tests -q      (from the repo root)
"""
import logging
import sys
import threading
import time

from ha_agent import ezviz, options


def run(command, stop_after=3.0):
    stop = threading.Event()
    bridge = ezviz.Bridge(stop, command=command).start()
    time.sleep(stop_after)
    stop.set()
    bridge.stop()
    return bridge


def test_off_unless_ezviz_cameras_are_configured():
    assert ezviz.wanted(options.Options(ezviz_cameras=[])) is False
    assert ezviz.wanted(options.Options(options.DEFAULTS)) is False
    assert ezviz.wanted(options.Options(ezviz_cameras=[{"name": "Gate"}])) is True


def test_bridge_output_reaches_the_addon_log(caplog):
    caplog.set_level(logging.INFO, logger="ezviz")
    run([sys.executable, "-u", "-c", "print('2026-10-18T00:00:00Z Gate: playing — frames flowing'); "
                               "import time; time.sleep(5)"], stop_after=1.5)
    assert "Gate: playing — frames flowing" in caplog.text
    assert "2026-10-18T00:00:00Z" not in caplog.text          # its timestamp is dropped


def test_settings_error_is_reported_once_not_retried(caplog):
    caplog.set_level(logging.INFO, logger="ezviz")
    run([sys.executable, "-u", "-c", "print('EZVIZ cameras are not set up: ezviz_app_key is empty'); "
                               "raise SystemExit(2)"], stop_after=1.5)
    assert caplog.text.count("ezviz_app_key is empty") == 1
    assert "Fix the ezviz_ options" in caplog.text
    assert "restarting" not in caplog.text


def test_crash_is_restarted(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="ezviz")
    # Make the restart pause short for the test.
    real_wait = threading.Event.wait
    monkeypatch.setattr(threading.Event, "wait", lambda self, t=None: real_wait(self, 0.05 if t else t))
    run([sys.executable, "-u", "-c", "print('started'); raise SystemExit(1)"], stop_after=1.0)
    assert caplog.text.count("started") >= 2
    assert "restarting" in caplog.text
