"""Many cameras: one checking budget shared fairly, rates change live, and the
screen says when the plan leaves cameras unwatched."""
from ha_agent import main
from ha_agent.ha_client import HAClient
from ha_agent.options import Options, DEFAULTS


def _options(**over):
    return Options({**DEFAULTS, **over})


def test_one_or_two_cameras_keep_the_full_rate():
    opts = _options(process_fps=2.0, max_total_fps=4.0)
    assert main.camera_fps(opts, 1) == 2.0
    assert main.camera_fps(opts, 2) == 2.0


def test_many_cameras_share_the_budget_instead_of_falling_behind():
    opts = _options(process_fps=2.0, max_total_fps=4.0)
    assert main.camera_fps(opts, 20) == 0.2          # every camera every 5 s
    assert main.camera_fps(opts, 50) * 50 <= 4.0 + 1e-9


class _Reader:
    _poll_interval = 0.5

    def start(self): ...
    def stop(self): ...
    def get_frame(self): return None
    def last_frame_age(self): return None


def test_rebalance_slows_running_cameras_without_restarting_them():
    from pipeline import EdgePipeline
    pipes = {f"camera.c{i}": EdgePipeline(
        {"camera_id": f"camera.c{i}", "name": f"C{i}", "stream_url": f"camera.c{i}"},
        detector=None, on_event=None, confidence_threshold=0.5, cooldown_seconds=30,
        process_fps=2.0, reader_factory=lambda url: _Reader()) for i in range(8)}
    fps = main.rebalance(pipes, _options(process_fps=2.0, max_total_fps=4.0))
    assert fps == 0.5
    for p in pipes.values():
        assert p._process_interval == 2.0 and p.reader._poll_interval == 2.0


def _published(client, *args):
    sent = {}
    client._post = lambda path, payload, what: sent.update(payload)
    client.publish_coverage(*args)
    return sent["attributes"]


def test_screen_says_when_the_plan_leaves_cameras_unwatched():
    attrs = _published(HAClient(token="t"), 1, 4, "free", 1, 2.0)
    assert attrs["not_watched"] == 3 and "free plan covers 1" in attrs["note"]


def test_no_note_when_every_camera_is_watched():
    assert _published(HAClient(token="t"), 4, 4, "pro", None, 1.0)["note"] == ""
