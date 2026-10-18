"""Runs the EZVIZ bridge (ezviz_bridge/bridge.mjs) inside the FiremeX add-on.

EZVIZ cameras with Video Encryption ON only play in EZVIZ's own player. The
bridge runs that official player headless, with the owner's EZVIZ Open Platform
keys and each camera's verification code, and adds every camera to Home
Assistant as an MJPEG camera. FiremeX then finds it through Home Assistant like
any other camera — nothing else in the add-on knows EZVIZ exists.

This module only starts the bridge when EZVIZ cameras are configured, copies
its output into the add-on log, and restarts it if it stops: a fire camera must
come back on its own.
"""
import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger("ezviz")

BRIDGE = os.environ.get("EZVIZ_BRIDGE", "/app/ezviz_bridge/bridge.mjs")

# bridge.mjs exits with this when its settings are wrong. Restarting cannot fix
# that, so the add-on says so and waits for the owner to change the settings.
CONFIG_ERROR = 2


def wanted(options) -> bool:
    return bool(options.get("ezviz_cameras"))


class Bridge:
    def __init__(self, stop: threading.Event, command=None):
        self._stop = stop
        self._command = command or ["node", BRIDGE]
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
                text=True, bufsize=1, env=os.environ.copy())
        except OSError as exc:
            logger.error(f"could not start the EZVIZ bridge: {exc}")
            return 1
        for line in self._proc.stdout:
            line = line.rstrip()
            if line:
                # The bridge prefixes its own ISO timestamp; ours is enough.
                logger.info(line.split(" ", 1)[1] if line[:4].isdigit() and " " in line else line)
        return self._proc.wait()
