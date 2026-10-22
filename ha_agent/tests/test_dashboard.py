"""The provisioned dashboard: only real entities, a plain status line, safe controls."""
import json

from ha_agent import setup_ha

CAMS = [("camera.ezviz_room", "EZVIZ Room")]


def _cards(view):
    for section in view.get("sections", []):
        yield from section.get("cards", [])


def test_dashboard_uses_no_entity_the_addon_never_creates():
    text = json.dumps(setup_ha.view_dashboard(CAMS))
    assert "sensor.firemex_confidence" not in text
    assert "sensor.firemex_camera" not in text


def test_no_view_badge_points_at_a_missing_entity():
    text = json.dumps(setup_ha.dashboard(CAMS))
    assert "sensor.firemex_confidence" not in text
    assert "sensor.firemex_camera" not in text


def test_dashboard_opens_with_a_plain_language_status_banner():
    first = next(_cards(setup_ha.view_dashboard(CAMS)))
    assert first["type"] == "markdown"
    for words in ("All clear", "Incident declared", "offline"):
        assert words in first["content"]


def test_dashboard_shows_each_cameras_live_picture():
    shown = [c.get("entity") for c in _cards(setup_ha.view_dashboard(CAMS))]
    assert "camera.ezviz_room" in shown


def test_camera_status_is_written_in_plain_words():
    cards = list(_cards(setup_ha.view_dashboard(CAMS)))
    status = [c for c in cards if c.get("type") == "markdown"
              and "ha-alert" not in c["content"]
              and setup_ha.status_sensor("camera.ezviz_room") in c["content"]]
    assert status
    for words in ("No fire seen", "Not sending pictures"):
        assert words in status[0]["content"]


def test_camera_picture_uses_stills_that_any_browser_can_show():
    pics = [c for c in _cards(setup_ha.view_dashboard(CAMS))
            if c.get("type") == "picture-entity" and c.get("entity") == "camera.ezviz_room"]
    assert pics and pics[0]["camera_view"] == "auto"


def test_response_controls_cannot_be_switched_by_one_tap():
    for tile in setup_ha._actuator_tiles():
        assert tile["tap_action"] == {"action": "more-info"}
        assert tile["icon_tap_action"] == {"action": "more-info"}


def test_dashboard_is_three_plain_tabs_without_setup_pages():
    views = setup_ha.dashboard(CAMS)["views"]
    assert [v["title"] for v in views] == ["Home", "Emergency", "History"]
    text = json.dumps(views)
    for setup_words in ("Add a camera", "Wiring", "Automations", "Camera setup"):
        assert setup_words not in text


def test_tabs_show_words_not_just_icons():
    assert all("icon" not in v for v in setup_ha.dashboard(CAMS)["views"])


def test_buttons_do_not_show_a_meaningless_state():
    text = json.dumps(setup_ha.dashboard(CAMS))
    tiles = []
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "tile" and str(node.get("entity", "")).startswith("input_button."):
                tiles.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(json.loads(text))
    assert tiles and all(t.get("hide_state") is True for t in tiles)


def test_response_names_fit_on_a_tile():
    assert all(len(t["name"]) <= 16 for t in setup_ha._actuator_tiles())


def test_dashboard_lists_only_the_cameras_firemex_watches():
    found = [("camera.ezviz_room", "EZVIZ Room"), ("camera.loading_dock", "Loading Dock")]
    assert setup_ha.cameras_to_show(found, {"camera.ezviz_room"}) == [("camera.ezviz_room", "EZVIZ Room")]
    assert setup_ha.cameras_to_show(found, None) == found


def test_live_picture_and_evidence_sit_side_by_side_on_one_screen():
    view = setup_ha.view_dashboard(CAMS)
    assert view["max_columns"] == 2
    live = [s for s in view["sections"] if any(c.get("entity") == "camera.ezviz_room" for c in s["cards"])]
    assert live and live[0].get("column_span", 1) == 1          # half the width, not all of it
    evidence = [s for s in view["sections"] if setup_ha.confirm_button("EZVIZ Room") in json.dumps(s)]
    assert evidence and evidence[0] is not live[0] and evidence[0].get("column_span", 1) == 1


def test_emergency_tab_has_no_redundant_incident_switch():
    tiles = [c for c in _cards(setup_ha.view_emergency(CAMS)) if c.get("type") == "tile"]
    assert all(t["entity"] != setup_ha.INCIDENT for t in tiles)


def test_history_lists_each_detection_once():
    logbook = next(c for c in _cards(setup_ha.view_history(CAMS)) if c["type"] == "logbook")
    assert "sensor.firemex_hazard" not in logbook["entities"]


def test_wide_sections_stack_their_cards_full_width():
    for view in setup_ha.dashboard(CAMS)["views"]:
        for section in view["sections"]:
            if section.get("column_span", 1) > 1:
                for card in section["cards"]:
                    if card["type"] != "heading":
                        assert card.get("grid_options") == {"columns": "full"}, card["type"]


def test_camera_status_is_read_before_its_picture():
    section = next(s for s in setup_ha.view_dashboard(CAMS)["sections"]
                   if any(c.get("entity") == "camera.ezviz_room" for c in s["cards"]))
    kinds = [c["type"] for c in section["cards"]]
    assert kinds.index("markdown") < kinds.index("picture-entity")
