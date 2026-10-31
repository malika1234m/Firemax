"""The provisioned dashboard: only real entities, a plain status line, safe controls."""
import json

from ha_agent import setup_ha

CAMS = [("camera.ezviz_room", "EZVIZ Room")]


def _flatten(card):
    """A card and everything nested in it (conditional, vertical-stack)."""
    yield card
    if "card" in card:
        yield from _flatten(card["card"])
    for inner in card.get("cards", []):
        yield from _flatten(inner)


def _cards(view):
    for section in view.get("sections", []):
        for card in section.get("cards", []):
            yield from _flatten(card)


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
    stack = next(c for c in _cards(setup_ha.view_dashboard(CAMS)) if c["type"] == "vertical-stack")
    status = [c for c in stack["cards"] if c.get("type") == "markdown"
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


def _alert_sections(view, label):
    return [s for s in view["sections"] if setup_ha.confirm_button(label) in json.dumps(s)]


def test_decision_panels_appear_only_for_the_camera_that_is_alerting():
    # With many cameras the operator must not scan one panel per camera.
    for view in (setup_ha.view_dashboard(CAMS), setup_ha.view_emergency(CAMS)):
        sections = _alert_sections(view, "EZVIZ Room")
        assert len(sections) == 1
        for card in sections[0]["cards"]:
            assert card["type"] == "conditional"
            assert setup_ha.status_sensor("camera.ezviz_room") in json.dumps(card["conditions"])


def test_camera_wall_fits_two_cameras_to_a_row():
    many = [(f"camera.cam_{i}", f"Cam {i}") for i in range(12)]
    wall = next(s for s in setup_ha.view_dashboard(many)["sections"]
                if any(c.get("heading") == "All cameras" for c in s["cards"]))
    tiles = [c for c in wall["cards"] if c["type"] == "vertical-stack"]
    assert len(tiles) == 12 and all(c["grid_options"] == {"columns": 6} for c in tiles)


def test_every_camera_is_on_the_wall_whatever_the_plan():
    many = [(f"camera.cam_{i}", f"Cam {i}") for i in range(50)]
    shown = {c.get("entity") for c in _cards(setup_ha.view_dashboard(many))}
    assert all(e in shown for e, _ in many)


def test_plan_coverage_is_shown_on_the_main_tabs():
    for view in (setup_ha.view_dashboard(CAMS), setup_ha.view_emergency(CAMS)):
        assert setup_ha.COVERAGE_SENSOR in json.dumps(view)


def test_emergency_tab_has_no_redundant_incident_switch():
    tiles = [c for c in _cards(setup_ha.view_emergency(CAMS)) if c.get("type") == "tile"]
    assert all(t["entity"] != setup_ha.INCIDENT for t in tiles)


def test_history_lists_each_detection_once():
    logbook = next(c for c in _cards(setup_ha.view_history(CAMS)) if c["type"] == "logbook")
    assert "sensor.firemex_hazard" not in logbook["entities"]


def test_wide_sections_stack_their_cards_full_width():
    for view in setup_ha.dashboard(CAMS)["views"]:
        for section in view["sections"]:
            if section.get("column_span", 1) > 1 and not any(
                    c.get("heading") == "All cameras" for c in section["cards"]):
                for card in section["cards"]:
                    if card["type"] != "heading":
                        assert card.get("grid_options") == {"columns": "full"}, card["type"]


def test_camera_status_is_read_before_its_picture():
    stack = next(c for c in _cards(setup_ha.view_dashboard(CAMS))
                 if c["type"] == "vertical-stack")
    kinds = [c["type"] for c in stack["cards"]]
    assert kinds.index("markdown") < kinds.index("picture-entity")
