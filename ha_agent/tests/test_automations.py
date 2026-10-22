"""Alerts reach people, not only the screen, and messages use real entities."""
import json

from ha_agent import setup_ha

CAMS = [("camera.ezviz_room", "EZVIZ Room")]
PEOPLE_MUST_HEAR = ["firemex_alert_review", "firemex_camera_offline",
                    "firemex_confirm_alert", "firemex_declare_incident"]


def test_every_alert_also_goes_to_phones_last_so_it_never_blocks_the_response():
    autos = setup_ha.automations(CAMS)
    for aid in PEOPLE_MUST_HEAR:
        last = autos[aid]["action"][-1]
        assert last["service"] == "notify.notify", aid
        assert last["continue_on_error"] is True, aid


def test_no_automation_reads_an_entity_the_addon_never_creates():
    text = json.dumps(setup_ha.automations(CAMS))
    assert "sensor.firemex_camera" not in text
    assert "sensor.firemex_confidence" not in text


def test_people_are_told_how_to_stay_safe_during_an_incident():
    text = json.dumps(setup_ha.view_emergency(CAMS))
    for advice in ("nearest exit", "lifts", "Do not try to put out a large fire"):
        assert advice in text


def test_nobody_is_sent_to_look_at_a_possible_fire():
    banner = setup_ha._status_banner(CAMS)["content"]
    assert "Do not go to check" in banner
