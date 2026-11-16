"""Regression tests for faults found in the 2026-11 Home Assistant add-on audit.

Each test failed before its fix (see FIREMEX_HOME_ASSISTANT_AUDIT.md, "Bugs fixed").
"""
import threading
import time

import numpy as np

from app.detection.detector import HazardDetector
from app.models import DetectionBox
from ha_agent import main
from pipeline import EdgePipeline


def _box(label, conf, source="model", x=100):
    return DetectionBox(x1=x, y1=100, x2=x + 200, y2=300, label=label, confidence=conf, source=source)


# ── the network's fire box must survive a rule agreeing with it ───────────

def test_colour_rule_cannot_suppress_the_networks_fire_box():
    det = object.__new__(HazardDetector)
    model_fire = _box("fire", 0.62)
    colour_fire = _box("fire", 0.80, source="colour", x=110)   # same flame, scored by area
    kept = det._deduplicate([model_fire, colour_fire])
    alerting = main.ClassFilteredDetector(det, ["fire", "smoke", "flame"]).is_hazard(kept)
    assert alerting == [model_fire]


def test_gas_rule_cannot_suppress_the_networks_fire_box_either_order():
    det = object.__new__(HazardDetector)
    model_fire = _box("fire", 0.55)
    gas = _box("gas_fire", 0.90, source="gas_colour", x=105)
    for boxes in ([model_fire, gas], [gas, model_fire]):
        kept = det._deduplicate(boxes)
        assert model_fire in kept and gas not in kept


def test_same_branch_duplicates_still_keep_the_higher_score():
    det = object.__new__(HazardDetector)
    low, high = _box("fire", 0.55), _box("fire", 0.85, x=105)
    assert det._deduplicate([low, high]) == [high]


def test_non_overlapping_boxes_from_all_branches_are_kept():
    det = object.__new__(HazardDetector)
    boxes = [_box("fire", 0.6, x=0), _box("fire", 0.9, source="colour", x=1000)]
    assert det._deduplicate(boxes) == boxes


# ── one network pass per frame; unused branches do not run ────────────────

class _Tensorish(list):
    def tolist(self):
        return list(self)


class _FakeBox:
    def __init__(self, cls, conf, xyxy):
        self.cls, self.conf, self.xyxy = [cls], [conf], [_Tensorish(xyxy)]


class _FakeModel:
    """Stands in for ultralytics.YOLO: counts calls, returns one fire box."""

    def __init__(self, names):
        self.names = names
        self.calls = 0

    def __call__(self, frame, verbose=False):
        self.calls += 1
        fire = [k for k, v in self.names.items() if v == "fire"][0]
        result = type("R", (), {})()
        result.names = self.names
        result.boxes = [_FakeBox(fire, 0.7, [10, 10, 60, 60])]
        return [result]


def _detector(names, branches):
    det = object.__new__(HazardDetector)
    det.model = _FakeModel(names)
    det.threshold = 0.5
    det._prev_gray = None
    det._model_lock = threading.Lock()
    det.branches = branches
    det._has_person = "person" in names.values()
    return det


def test_network_runs_once_per_frame_even_with_person_down_on():
    det = _detector({0: "fire", 1: "person"}, frozenset({"model", "pose"}))
    det.detect(np.zeros((120, 160, 3), np.uint8))
    assert det.model.calls == 1


def test_rule_branches_are_skipped_when_not_requested():
    det = _detector({0: "smoke", 1: "fire", 2: "small_flame"}, frozenset({"model"}))
    frame = np.zeros((200, 200, 3), np.uint8)
    frame[40:160, 40:160] = (0, 120, 255)        # bright orange: the colour rule would fire
    boxes = det.detect(frame)
    assert [b.source for b in boxes] == ["model"]


def test_branches_for_maps_opt_in_classes_to_their_branch():
    assert main.branches_for(["fire", "smoke", "flame"]) == {"model"}
    assert main.branches_for(["fire", "colour_fire", "gas_fire", "gas_shimmer", "person_down"]) == \
        {"model", "colour", "gas_colour", "flow", "pose"}


# ── a failing cycle must not end detection on that camera ─────────────────

class _Reader:
    _poll_interval = None

    def __init__(self, url):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def get_frame(self):
        return np.zeros((10, 10, 3), np.uint8)

    def last_frame_age(self):
        return 0.1


class _FlakyDetector:
    threshold = 0.5

    def __init__(self, fail_on):
        self.calls, self.fail_on = 0, fail_on

    def detect(self, frame):
        self.calls += 1
        if self.calls in self.fail_on:
            raise RuntimeError("transient inference error")
        return [DetectionBox(x1=0, y1=0, x2=5, y2=5, label="fire", confidence=0.9)]

    def is_hazard(self, d):
        return d


def _wait(seconds):
    # Not time.sleep: the tests speed that up for the pipeline thread.
    threading.Event().wait(seconds)


def _run(pipeline, seconds):
    pipeline.start()
    _wait(seconds)
    pipeline.stop()


def test_pipeline_keeps_detecting_after_an_exception(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: threading.Event().wait(min(s, 0.01)))
    events = []
    det = _FlakyDetector(fail_on={2})
    p = EdgePipeline({"camera_id": "camera.x", "name": "X", "stream_url": "camera.x"},
                     det, events.append, 0.5, 0, reader_factory=_Reader, process_fps=50)
    _run(p, 0.5)
    assert det.calls > 3, "detection stopped after the first exception"
    assert p.errors == 1
    assert len(events) >= 2


def test_health_reports_not_detecting_while_cycles_fail(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: threading.Event().wait(min(s, 0.01)))
    det = _FlakyDetector(fail_on=set(range(1, 10_000)))
    p = EdgePipeline({"camera_id": "camera.x", "name": "X", "stream_url": "camera.x"},
                     det, lambda e: None, 0.5, 0, reader_factory=_Reader, process_fps=50)
    p.start()
    _wait(0.2)
    health = p.health()
    p.stop()
    assert health["online"] is True          # frames do arrive …
    assert health["detecting"] is False      # … but nothing is being checked


def test_alert_is_retried_when_delivery_fails_instead_of_waiting_a_cooldown(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: threading.Event().wait(min(s, 0.01)))
    delivered, attempts = [], []

    def on_event(event):
        attempts.append(event)
        if len(attempts) == 1:
            raise ConnectionError("Home Assistant restarting")
        delivered.append(event)

    p = EdgePipeline({"camera_id": "camera.x", "name": "X", "stream_url": "camera.x"},
                     _FlakyDetector(fail_on=set()), on_event, 0.5, 600,
                     reader_factory=_Reader, process_fps=50)
    _run(p, 0.3)
    assert len(delivered) == 1               # second try went through, despite the 600 s cooldown


# ── start-up waits for Home Assistant instead of exiting ──────────────────

class _Client:
    def __init__(self, fail_times):
        self.fail_times, self.pings = fail_times, 0

    def ping(self):
        self.pings += 1
        return self.pings > self.fail_times


def test_startup_waits_for_home_assistant_instead_of_exiting():
    client = _Client(fail_times=3)
    assert main.wait_for_home_assistant(client, threading.Event(), retry_seconds=0.01) is True
    assert client.pings == 4


def test_startup_wait_ends_cleanly_when_the_add_on_is_stopped():
    stop = threading.Event()
    threading.Timer(0.05, stop.set).start()
    assert main.wait_for_home_assistant(_Client(fail_times=10**9), stop, retry_seconds=0.01) is False


# ── secrets in the Configuration tab are masked ───────────────────────────

def test_secret_options_are_masked_in_the_configuration_tab():
    # "str" options are shown in clear in Home Assistant's UI; "password" ones
    # are masked. The licence key is the paid entitlement, so a screenshot of
    # the settings must not leak it.
    import os
    import yaml
    config = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "..", "..",
                                              "addon", "firemex-local", "config.yaml")))
    for secret in ("licence_key", "ezviz_app_secret"):
        assert config["schema"][secret].startswith("password"), secret


# ── a refused token is reported as such, never as "not reachable" ─────────

def test_refused_token_is_named_in_the_startup_log_without_the_token(caplog):
    import httpx
    from ha_agent.ha_client import HAClient

    secret = "s3cret-token-value"
    client = HAClient(base_url="http://ha.test/api", token=secret)
    client._client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(401, text="401: Unauthorized")))
    stop = threading.Event()
    threading.Timer(0.05, stop.set).start()
    with caplog.at_level("WARNING"):
        assert main.wait_for_home_assistant(client, stop, retry_seconds=0.01) is False
    assert "refused the add-on's API token (HTTP 401)" in caplog.text
    assert secret not in caplog.text


def test_unreachable_home_assistant_says_so():
    import httpx
    from ha_agent.ha_client import HAClient

    def boom(request):
        raise httpx.ConnectError("connection refused")
    client = HAClient(base_url="http://ha.test/api", token="t")
    client._client = httpx.Client(transport=httpx.MockTransport(boom))
    assert client.ping() is False
    assert "cannot reach Home Assistant" in client.last_error


# ── the "camera offline" notification comes down when cameras come back ───

class _Pipe:
    def __init__(self, age):
        self.age = age

    def health(self):
        return {"online": self.age < 15, "last_frame_age_s": self.age, "fps": 2.0, "detecting": True}


class _Recorder:
    def __init__(self):
        self.offline, self.dismissed = [], 0

    def publish_camera_offline(self, entity_id, *a):
        self.offline.append(entity_id)

    def dismiss_offline_notification(self):
        self.dismissed += 1

    def publish_camera(self, *a):
        pass


def test_offline_notification_is_dismissed_only_when_every_camera_is_back():
    from types import SimpleNamespace
    opts = SimpleNamespace(camera_offline_after_seconds=60, clear_after_seconds=120)
    pipes = {"camera.a": _Pipe(90), "camera.b": _Pipe(90)}
    states = {"camera.a": main.CameraState("A"), "camera.b": main.CameraState("B")}
    client = _Recorder()
    now = time.time()

    main.update_camera_health(client, opts, pipes, states, now)
    assert sorted(client.offline) == ["camera.a", "camera.b"]

    pipes["camera.a"].age = 0.5                       # A back, B still down
    main.update_camera_health(client, opts, pipes, states, now)
    assert client.dismissed == 0                      # B's outage must stay on screen

    pipes["camera.b"].age = 0.5                       # both back
    main.update_camera_health(client, opts, pipes, states, now)
    assert client.dismissed == 1
    assert all(s.hazard == "clear" for s in states.values())
