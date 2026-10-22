"""A camera is offline only after being silent for camera_offline_after_seconds."""
from ha_agent import main


def test_a_brief_gap_is_not_offline():
    assert not main.camera_silent({"last_frame_age_s": 20.0}, started_at=0, now=500, after=60)


def test_silent_longer_than_the_setting_is_offline():
    assert main.camera_silent({"last_frame_age_s": 61.0}, started_at=0, now=500, after=60)


def test_never_sent_a_frame_is_offline_only_after_the_grace_period():
    assert not main.camera_silent({"last_frame_age_s": None}, started_at=0, now=30, after=60)
    assert main.camera_silent({"last_frame_age_s": None}, started_at=0, now=61, after=60)
