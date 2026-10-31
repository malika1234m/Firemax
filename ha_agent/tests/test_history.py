"""Detection history: every alert keeps its own photo, the list is bounded and
survives a restart, and the dashboard shows it."""
import base64
import json
import os

from ha_agent import ha_client, history, setup_ha

CAMS = [("camera.ezviz_room", "EZVIZ Room")]
JPEG = base64.b64encode(b"\xff\xd8fake\xff\xd9").decode()


def _event(confidence=0.8):
    return {"camera_id": "camera.ezviz_room", "camera_name": "EZVIZ Room",
            "hazard_type": "fire", "confidence": confidence, "frame_b64": JPEG}


def test_each_detection_keeps_its_own_photo_newest_first(tmp_path):
    path = tmp_path / "detections.json"
    history.record(_event(0.6), "2026-10-26T20:17:44+00:00", str(tmp_path), str(path))
    entries = history.record(_event(0.9), "2026-10-26T20:18:31+00:00", str(tmp_path), str(path))
    assert [e["confidence"] for e in entries] == [0.9, 0.6]
    photos = [e["photo"] for e in entries]
    assert len(set(photos)) == 2 and all(p.startswith("/local/firemex/history/") for p in photos)
    for p in photos:
        assert (tmp_path / "history" / os.path.basename(p)).exists()


def test_old_detections_and_their_photos_are_removed(tmp_path):
    path = tmp_path / "detections.json"
    for i in range(5):
        history.record(_event(), f"2026-10-26T20:1{i}:00+00:00", str(tmp_path), str(path), max_entries=3)
    assert len(history.load(str(path))) == 3
    assert len(os.listdir(tmp_path / "history")) == 3


def test_history_survives_a_restart(tmp_path):
    path = tmp_path / "detections.json"
    history.record(_event(), "2026-10-26T20:17:44+00:00", str(tmp_path), str(path))
    assert history.load(str(path))[0]["camera"] == "EZVIZ Room"


def test_a_broken_history_file_never_stops_an_alert(tmp_path):
    path = tmp_path / "detections.json"
    path.write_text("not json")
    entries = history.record(_event(), "2026-10-26T20:17:44+00:00", str(tmp_path), str(path))
    assert len(entries) == 1


def test_dashboard_reads_the_sensor_the_addon_publishes():
    assert setup_ha.HISTORY_SENSOR == ha_client.HISTORY_SENSOR


def test_history_tab_shows_detection_photos():
    text = json.dumps(setup_ha.view_history(CAMS))
    assert setup_ha.HISTORY_SENSOR in text and "<img" in text


def test_emergency_tab_shows_where_fire_was_seen_for_every_camera():
    view = setup_ha.view_emergency(CAMS)
    cards = []
    def walk(c):
        cards.append(c)
        if "card" in c:
            walk(c["card"])
        for inner in c.get("cards", []):
            walk(inner)
    for s in view["sections"]:
        for c in s["cards"]:
            walk(c)
    assert any(c.get("entity") == setup_ha.snapshot_camera("camera.ezviz_room") for c in cards)
    declare = [c for c in cards if c.get("entity") == setup_ha.confirm_button("EZVIZ Room")]
    assert declare, "operator must be able to declare a fire on this camera"
    # starts the whole building response, so never on a single tap
    assert declare[0]["tap_action"] == {"action": "more-info"}
