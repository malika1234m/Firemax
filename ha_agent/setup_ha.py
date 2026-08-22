"""Provision the FiremeX operator workflow inside Home Assistant.

Creates the helpers, automations, snapshot cameras and dashboard that turn raw
detections into a reviewed operator workflow. Idempotent — re-running skips
anything that already exists.

Two ways in:

  * The add-on calls provision() itself on start, authenticating through the
    Supervisor proxy with SUPERVISOR_TOKEN. A customer installs the add-on,
    presses Start, and the dashboard is there. Anything less is not a product.

  * Standalone, against any Home Assistant (including HA Container, which has
    no Supervisor and therefore cannot run add-ons at all):

        HA_URL=http://localhost:8123 HA_TOKEN=<long-lived token> \
            python ha_agent/setup_ha.py

THE RULE THIS ENCODES
---------------------
FiremeX raises ALERTS. Only an operator declares an INCIDENT. Sprinklers, the
evacuation siren and the fire brigade hang off `input_boolean.firemex_incident`,
which nothing but the operator's confirm button turns on. No automation here
triggers an actuator from a detection event, and none should be added that
does: the model is confident and sometimes wrong, and a false sprinkler
discharge is its own emergency.

The actuators created here are `input_boolean` stand-ins so the workflow can be
demonstrated without real hardware. Replace them with your real `switch.*`,
`siren.*` and `notify.*` targets in the declare-incident automation.
"""
import asyncio
import json
import os
import urllib.request

# Resolved once by configure(); module-level so the helpers below stay simple.
HA_URL = ""
TOKEN = ""
WS_URL = ""


def configure(url: str | None = None, token: str | None = None) -> None:
    """Decide which Home Assistant to talk to, and how.

    Inside an add-on there is no URL or long-lived token to configure: the
    Supervisor injects SUPERVISOR_TOKEN and proxies Core at
    http://supervisor/core. Outside one, an explicit URL + long-lived token is
    required. Preferring an explicit argument over the environment lets the
    add-on pass its own client credentials straight in.
    """
    global HA_URL, TOKEN, WS_URL

    supervisor = os.environ.get("SUPERVISOR_TOKEN", "")
    if url:
        HA_URL = url.rstrip("/")
    elif os.environ.get("HA_URL"):
        HA_URL = os.environ["HA_URL"].rstrip("/")
    elif supervisor:
        HA_URL = "http://supervisor/core"
    else:
        HA_URL = "http://localhost:8123"

    TOKEN = token or os.environ.get("HA_TOKEN") or supervisor or ""
    if not TOKEN:
        token_file = os.path.expanduser("~/.firemex_ha_token")
        if os.path.exists(token_file):
            TOKEN = open(token_file).read().strip()
    if not TOKEN:
        raise SystemExit(
            "No Home Assistant credentials. Inside an add-on this comes from "
            "SUPERVISOR_TOKEN; standalone, set HA_TOKEN to a long-lived access "
            "token (Profile -> Security -> Long-lived access tokens)."
        )

    WS_URL = HA_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"


PIN_ALL = "All cameras"

BUTTONS = [("FiremeX Declare Incident", "mdi:fire-alert"),
           ("FiremeX Stand Down", "mdi:check-circle-outline")]
BOOLEANS = [("FiremeX Incident", "mdi:alert-octagon"),
            ("Fire Sprinklers", "mdi:sprinkler-fire"),
            ("Evacuation Siren", "mdi:bullhorn"),
            ("Fire Brigade Called", "mdi:fire-truck")]


def rest(path, payload=None, method="GET"):
    req = urllib.request.Request(
        f"{HA_URL}/api{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode()
        return r.status, (json.loads(body) if body.strip().startswith(("{", "[")) else body)


# FiremeX republishes its annotated snapshots as local_file cameras. Excluded
# here for the same reason the agent excludes them: they are FiremeX's own
# output, not sources to watch or build alert cards for.
SNAPSHOT_CAMERA_PREFIX = "camera.firemex_snapshot_"


def discover_cameras():
    _, states = rest("/states")
    return [(s["entity_id"], s["attributes"].get("friendly_name") or s["entity_id"].split(".", 1)[1])
            for s in states
            if s["entity_id"].startswith("camera.")
            and not s["entity_id"].startswith(SNAPSHOT_CAMERA_PREFIX)
            and s["state"] not in ("unavailable", "unknown")]


def status_sensor(camera_entity: str) -> str:
    return "sensor.firemex_cam_" + camera_entity.split(".", 1)[1]


def snapshot_camera(camera_entity: str) -> str:
    """The local_file camera showing that camera's annotated evidence frame."""
    return "camera.firemex_snapshot_" + camera_entity.split(".", 1)[1]


def confirm_button_name(label: str) -> str:
    return f"FiremeX Confirm {label}"


def confirm_button(label: str) -> str:
    return "input_button." + confirm_button_name(label).lower().replace(" ", "_")


# ── automations ────────────────────────────────────────────────────────────

def automations(cameras):
    # An input_button trigger fires on ANY state change of that entity —
    # including the entity being re-registered after a Home Assistant restart or
    # an automation reload. Unguarded, reloading automations DECLARED AN INCIDENT
    # and turned the sprinklers on with nobody touching anything. Observed, not
    # theoretical.
    #
    # The guard keys on the NEW state, not the old one. An input_button's state
    # IS the moment it was pressed, so a genuine press always lands within a
    # second or two of now; a re-registration either goes to "unknown" or
    # restores a stale timestamp. An earlier version tested from_state instead,
    # which silently swallowed the FIRST press of every freshly created button —
    # its previous state is "unknown" too.
    guard = [{"condition": "template", "value_template": (
        "{{ trigger.to_state is not none "
        "and trigger.to_state.state not in ['unknown', 'unavailable'] "
        "and (as_timestamp(now()) - as_timestamp(trigger.to_state.state, 0)) < 10 }}")}]

    # Per-camera confirm buttons all feed ONE automation. The camera is read
    # back off whichever button fired, so adding a camera does not mean adding
    # another near-identical automation to keep in step.
    confirm = {
        "alias": "FiremeX — Operator confirms an alert",
        "description": ("Operator reviewed the evidence snapshot for one camera and "
                        "confirmed it. This is what actuates the building."),
        "mode": "single",
        "trigger": [{"platform": "state", "entity_id": confirm_button(label)}
                    for _, label in cameras],
        "condition": guard,
        "action": [
            {"variables": {"cam": ("{{ trigger.to_state.attributes.friendly_name "
                                   "| replace('FiremeX Confirm ', '') }}")}},
            {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.firemex_incident"}},
            {"event": "firemex_incident", "event_data": {"declared_by": "operator",
                                                         "camera": "{{ cam }}"}},
            {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.fire_sprinklers"}},
            {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.evacuation_siren"}},
            {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.fire_brigade_called"}},
            {"service": "persistent_notification.dismiss", "data": {"notification_id": "firemex_alert"}},
            {"service": "persistent_notification.create", "data": {
                "title": "INCIDENT DECLARED",
                "notification_id": "firemex_incident",
                "message": ("Confirmed on {{ cam }}.\n"
                            "Sprinklers ON · Evacuation siren ON · Fire brigade called.")}},
        ],
    }

    # Put the alerting camera on screen without the operator hunting for it.
    # Only real hazards move the pin: if colour-branch noise could yank it, the
    # pin would thrash and become useless exactly when it matters.
    autopin = {
        "alias": "FiremeX — Pin the alerting camera",
        "description": "Surfaces the camera that raised the alert on the Live Feed wall.",
        "mode": "queued", "max": 10,
        "trigger": [{"platform": "event", "event_type": "firemex_hazard"}],
        "condition": [
            {"condition": "template", "value_template": (
                "{{ trigger.event.data.hazard_type in ['fire', 'smoke', 'flame'] }}")},
            # Selecting an option the input_select does not have raises an
            # error and aborts the automation, so check before selecting.
            {"condition": "template", "value_template": (
                "{{ trigger.event.data.camera_name in "
                "state_attr('input_select.firemex_pinned_camera', 'options') }}")},
        ],
        "action": [
            {"service": "input_select.select_option",
             "target": {"entity_id": "input_select.firemex_pinned_camera"},
             "data": {"option": "{{ trigger.event.data.camera_name }}"}},
        ],
    }

    return {
        "firemex_confirm_alert": confirm,
        "firemex_autopin_camera": autopin,
        # A detection arrives. Tell the operator. Actuate NOTHING.
        "firemex_alert_review": {
            "alias": "FiremeX — Alert raised (review required)",
            "description": "A detection needs human review. Deliberately actuates nothing.",
            "mode": "queued", "max": 25,
            "trigger": [{"platform": "event", "event_type": "firemex_hazard"}],
            "action": [{"service": "persistent_notification.create", "data": {
                "title": "FiremeX alert — review required",
                "notification_id": "firemex_alert",
                "message": ("{{ trigger.event.data.hazard_type | upper }} on "
                            "{{ trigger.event.data.camera_name }} at "
                            "{{ (trigger.event.data.confidence * 100) | int }}% confidence.\n\n"
                            "Open the FiremeX dashboard and confirm before declaring an incident.")}}],
        },
        # A camera stopped delivering frames — silence is not safety.
        "firemex_camera_offline": {
            "alias": "FiremeX — Camera offline",
            "description": "A camera stopped delivering frames and is no longer watched.",
            "mode": "queued", "max": 25,
            "trigger": [{"platform": "event", "event_type": "firemex_camera_offline"}],
            "action": [{"service": "persistent_notification.create", "data": {
                "title": "FiremeX — camera offline",
                "notification_id": "firemex_camera_offline",
                "message": ("{{ trigger.event.data.camera_name }} has stopped delivering "
                            "frames and is no longer being monitored.")}}],
        },
        # THE HUMAN GATE. Everything destructive hangs off this button.
        # Replace the input_boolean targets with your real switches/sirens.
        "firemex_declare_incident": {
            "alias": "FiremeX — Operator declares incident",
            "description": "Operator confirmed a real fire. This actuates the building.",
            "mode": "single",
            "trigger": [{"platform": "state", "entity_id": "input_button.firemex_declare_incident"}],
            # See the `guard` note above — same reasoning, same expression.
            "condition": [{"condition": "template", "value_template": (
                "{{ trigger.to_state is not none "
                "and trigger.to_state.state not in ['unknown', 'unavailable'] "
                "and (as_timestamp(now()) - as_timestamp(trigger.to_state.state, 0)) < 10 }}")}],
            "action": [
                {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.firemex_incident"}},
                {"event": "firemex_incident", "event_data": {"declared_by": "operator"}},
                {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.fire_sprinklers"}},
                {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.evacuation_siren"}},
                {"service": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.fire_brigade_called"}},
                {"service": "persistent_notification.dismiss", "data": {"notification_id": "firemex_alert"}},
                {"service": "persistent_notification.create", "data": {
                    "title": "INCIDENT DECLARED", "notification_id": "firemex_incident",
                    "message": ("Sprinklers ON · Evacuation siren ON · Fire brigade called.\n"
                                "Trigger: {{ states('sensor.firemex_hazard') }} on "
                                "{{ states('sensor.firemex_camera') }} "
                                "({{ states('sensor.firemex_confidence') }}%).")}},
            ],
        },
        "firemex_stand_down": {
            "alias": "FiremeX — Stand down",
            "description": "Incident over, or declared in error. Reverses every actuator.",
            "mode": "single",
            "trigger": [{"platform": "state", "entity_id": "input_button.firemex_stand_down"}],
            # See the `guard` note above — same reasoning, same expression.
            "condition": [{"condition": "template", "value_template": (
                "{{ trigger.to_state is not none "
                "and trigger.to_state.state not in ['unknown', 'unavailable'] "
                "and (as_timestamp(now()) - as_timestamp(trigger.to_state.state, 0)) < 10 }}")}],
            "action": [
                {"service": "input_boolean.turn_off", "target": {"entity_id": [
                    "input_boolean.firemex_incident", "input_boolean.fire_sprinklers",
                    "input_boolean.evacuation_siren", "input_boolean.fire_brigade_called"]}},
                {"service": "persistent_notification.dismiss", "data": {"notification_id": "firemex_incident"}},
                {"service": "persistent_notification.dismiss", "data": {"notification_id": "firemex_alert"}},
            ],
        },
    }


# ── dashboard ──────────────────────────────────────────────────────────────

def _status_tiles(cameras):
    """One tile per camera, showing that camera's own hazard state.

    Deliberately placed ABOVE the pictures everywhere it appears: an operator
    scanning a wall of six cameras needs to know WHICH one is alerting before
    they start looking at images.
    """
    return [{"type": "tile", "entity": status_sensor(e), "name": n,
             "icon": "mdi:cctv", "color": "red"} for e, n in cameras]


def _actuator_tiles():
    return [
        {"type": "tile", "entity": "input_boolean.fire_sprinklers",
         "name": "Sprinklers", "icon": "mdi:sprinkler-fire", "color": "blue"},
        {"type": "tile", "entity": "input_boolean.evacuation_siren",
         "name": "Evacuation siren", "icon": "mdi:bullhorn", "color": "amber"},
        {"type": "tile", "entity": "input_boolean.fire_brigade_called",
         "name": "Fire brigade", "icon": "mdi:fire-truck", "color": "red"},
    ]


def _alert_badges():
    return [
        {"type": "entity", "entity": "input_boolean.firemex_incident", "name": "Incident"},
        {"type": "entity", "entity": "sensor.firemex_hazard", "name": "Alert"},
        {"type": "entity", "entity": "sensor.firemex_confidence", "name": "Confidence"},
        {"type": "entity", "entity": "sensor.firemex_camera", "name": "Camera"},
    ]


def view_dashboard(cameras):
    return {
        "title": "Dashboard", "path": "dashboard",
        "theme": "FiremeX", "type": "sections", "max_columns": 3,
        "badges": _alert_badges(),
        "sections": [
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Current state", "heading_style": "title",
                 "icon": "mdi:fire-alert"},
                {"type": "tile", "entity": "sensor.firemex_hazard", "name": "Hazard",
                 "icon": "mdi:fire-alert", "color": "red"},
                {"type": "tile", "entity": "sensor.firemex_confidence", "name": "Confidence",
                 "icon": "mdi:gauge", "color": "amber"},
                {"type": "tile", "entity": "sensor.firemex_camera", "name": "Source camera",
                 "icon": "mdi:cctv", "color": "cyan"},
                {"type": "tile", "entity": "input_boolean.firemex_incident",
                 "name": "Incident declared", "icon": "mdi:alert-octagon", "color": "red"},
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Cameras", "heading_style": "title",
                 "icon": "mdi:cctv"}, *_status_tiles(cameras)]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Response", "heading_style": "title",
                 "icon": "mdi:home-lightning-bolt"}, *_actuator_tiles()]},
            {"type": "grid", "column_span": 3, "cards": [
                {"type": "heading", "heading": "Recent activity", "heading_style": "title",
                 "icon": "mdi:history"},
                {"type": "logbook", "hours_to_show": 6,
                 "entities": ["sensor.firemex_hazard", "input_boolean.firemex_incident"]},
            ]},
        ],
    }


def view_live_feed(cameras):
    cards = [
        {"type": "heading", "heading": "Live feed", "heading_style": "title", "icon": "mdi:video"},
        {"type": "entities", "title": "Pin a camera", "entities": [
            {"entity": "input_select.firemex_pinned_camera", "name": "Pinned"}]},
        *_status_tiles(cameras),
    ]
    for entity, label in cameras:
        cards.append({"type": "conditional",
                      "conditions": [{"condition": "state",
                                      "entity": "input_select.firemex_pinned_camera",
                                      "state": label}],
                      "card": {"type": "picture-entity", "entity": entity,
                               "camera_view": "auto", "name": f"PINNED — {label}",
                               "show_state": False}})
    cards.append({"type": "heading", "heading": "All cameras",
                  "heading_style": "subtitle", "icon": "mdi:grid"})
    for entity, label in cameras:
        cards.append({"type": "picture-entity", "entity": entity, "camera_view": "auto",
                      "name": label, "show_state": False})
    return {"title": "Live Feed", "path": "live-feed",
            "theme": "FiremeX", "type": "sections", "max_columns": 3,
            "badges": [{"type": "entity", "entity": status_sensor(e), "name": n}
                       for e, n in cameras],
            "sections": [{"type": "grid", "column_span": 3, "cards": cards}]}


def view_alerts(cameras):
    """The alert queue: one card per camera, each carrying its own evidence
    snapshot and its own confirm button.

    A confidence number is not something a human can confirm or reject. The
    annotated frame is — it shows what the model actually boxed, so an operator
    can see a real fire, or see that it has boxed a red bollard, and decide.
    That is the entire justification for the human gate existing at all.
    """
    sections = []
    for entity, label in cameras:
        sections.append({"type": "grid", "cards": [
            {"type": "heading", "heading": label, "heading_style": "title",
             "icon": "mdi:cctv"},
            # The evidence, first and largest — it is what the decision is made on.
            {"type": "picture-entity", "entity": snapshot_camera(entity),
             "camera_view": "auto", "name": f"{label} — detection snapshot",
             "show_state": False},
            {"type": "tile", "entity": status_sensor(entity), "name": "Detected",
             "icon": "mdi:fire-alert", "color": "red"},
            {"type": "entities", "state_color": True, "entities": [
                {"type": "attribute", "entity": status_sensor(entity),
                 "attribute": "confidence", "name": "Confidence"},
                {"type": "attribute", "entity": status_sensor(entity),
                 "attribute": "last_detection", "name": "Detected at"},
                {"type": "attribute", "entity": status_sensor(entity),
                 "attribute": "online", "name": "Camera online"},
            ]},
            {"type": "tile", "entity": confirm_button(label),
             "name": f"CONFIRM — declare incident", "icon": "mdi:check-decagram",
             "color": "red", "tap_action": {"action": "toggle"}},
        ]})

    sections.append({"type": "grid", "column_span": 3, "cards": [
        {"type": "heading", "heading": "Current alert", "heading_style": "title",
         "icon": "mdi:bell-alert"},
        {"type": "tile", "entity": "sensor.firemex_hazard", "name": "Hazard",
         "icon": "mdi:fire-alert", "color": "red"},
        {"type": "tile", "entity": "sensor.firemex_confidence", "name": "Confidence",
         "icon": "mdi:gauge", "color": "amber"},
        {"type": "tile", "entity": "sensor.firemex_camera", "name": "Camera",
         "icon": "mdi:cctv", "color": "cyan"},
        {"type": "tile", "entity": "input_button.firemex_stand_down",
         "name": "STAND DOWN", "icon": "mdi:check-circle-outline", "color": "green",
         "tap_action": {"action": "toggle"}},
        {"type": "history-graph", "hours_to_show": 6,
         "entities": [{"entity": "sensor.firemex_hazard", "name": "Alert"}] +
                     [{"entity": status_sensor(e), "name": n} for e, n in cameras]},
        {"type": "logbook", "hours_to_show": 6, "entities": ["sensor.firemex_hazard"]},
    ]})

    return {
        "title": "Alerts", "path": "alerts",
        "theme": "FiremeX", "type": "sections", "max_columns": 3,
        "badges": _alert_badges(),
        "sections": sections,
    }


def view_incidents(cameras):
    """Incident view, organised around the one question an operator has:
    *is something happening right now, and what do I do about it?*

    The view changes shape with the incident state rather than showing every
    control all the time. When nothing is happening it is a calm history page
    with the means to declare; once an incident is declared it becomes a
    response board with STAND DOWN as the only prominent action. Showing
    "declare" and "stand down" side by side at all times is how someone presses
    the wrong one under pressure.
    """
    def when(state, card):
        return {"type": "conditional",
                "conditions": [{"condition": "state",
                                "entity": "input_boolean.firemex_incident",
                                "state": state}],
                "card": card}

    # ── 1. Status: one headline, then the detail that matters in that state ──
    status = [
        {"type": "heading", "heading": "Incident status", "heading_style": "title",
         "icon": "mdi:alert-octagon"},
        {"type": "tile", "entity": "input_boolean.firemex_incident",
         "name": "Incident", "icon": "mdi:alert-octagon", "color": "red"},
        when("on", {"type": "entities", "title": "What triggered this",
                    "state_color": True, "entities": [
                        {"entity": "sensor.firemex_hazard", "name": "Hazard"},
                        {"entity": "sensor.firemex_camera", "name": "Camera"},
                        {"entity": "sensor.firemex_confidence", "name": "Confidence"},
                        {"type": "attribute", "entity": "sensor.firemex_hazard",
                         "attribute": "timestamp", "name": "Detected at"},
                    ]}),
        when("off", {"type": "entities", "title": "No active incident",
                     "state_color": True, "entities": [
                         {"entity": "sensor.firemex_hazard", "name": "Latest alert"},
                         {"entity": "sensor.firemex_camera", "name": "On camera"},
                         {"entity": "sensor.firemex_confidence", "name": "Confidence"},
                     ]}),
    ]

    # ── 2. Response: what the building actually did ─────────────────────────
    response = [
        {"type": "heading", "heading": "Building response", "heading_style": "title",
         "icon": "mdi:home-lightning-bolt"},
        *_actuator_tiles(),
    ]

    # ── 3. Controls: only the action that makes sense right now ─────────────
    controls = [
        {"type": "heading", "heading": "Controls", "heading_style": "title",
         "icon": "mdi:gesture-tap-button"},
        when("on", {"type": "tile", "entity": "input_button.firemex_stand_down",
                    "name": "STAND DOWN", "icon": "mdi:check-circle-outline",
                    "color": "green", "tap_action": {"action": "toggle"}}),
    ]
    # Declaring is per camera, because the evidence an operator confirms belongs
    # to a camera. The unattached button below is the exception, not the norm.
    for _, label in cameras:
        controls.append(when("off", {
            "type": "tile", "entity": confirm_button(label),
            "name": f"Confirm — {label}", "icon": "mdi:check-decagram",
            "color": "red", "tap_action": {"action": "toggle"}}))
    controls.append(when("off", {
        "type": "tile", "entity": "input_button.firemex_declare_incident",
        "name": "Declare without a camera", "icon": "mdi:fire-alert",
        "color": "orange", "tap_action": {"action": "toggle"}}))

    # ── 4. History ──────────────────────────────────────────────────────────
    history = [
        {"type": "heading", "heading": "Incident history", "heading_style": "title",
         "icon": "mdi:history"},
        {"type": "history-graph", "hours_to_show": 12, "entities": [
            {"entity": "input_boolean.firemex_incident", "name": "Incident"},
            {"entity": "input_boolean.fire_sprinklers", "name": "Sprinklers"},
            {"entity": "input_boolean.evacuation_siren", "name": "Siren"},
            {"entity": "input_boolean.fire_brigade_called", "name": "Brigade"}]},
        {"type": "logbook", "hours_to_show": 12, "entities": [
            "input_boolean.firemex_incident", "input_boolean.fire_sprinklers",
            "input_boolean.evacuation_siren", "input_boolean.fire_brigade_called"]},
    ]

    return {
        "title": "Incidents", "path": "incidents",
        "theme": "FiremeX", "type": "sections", "max_columns": 3,
        "badges": _alert_badges(),
        "sections": [
            {"type": "grid", "cards": status},
            {"type": "grid", "cards": response},
            {"type": "grid", "cards": controls},
            {"type": "grid", "column_span": 3, "cards": history},
        ],
    }


def view_cameras(cameras):
    """Camera management.

    FiremeX does not own cameras — Home Assistant does — so "Add camera" hands
    off to HA's own integration flow rather than pretending to be a second
    place cameras can be configured.

    Per-camera detail is rendered as one entities card PER CAMERA. A single
    card using `type: section` rows to group several cameras blanked the whole
    view on this Home Assistant build.
    """
    cards = [
        {"type": "heading", "heading": "Cameras", "heading_style": "title",
         "icon": "mdi:camera"},
        *_status_tiles(cameras),
    ]
    for entity, label in cameras:
        sensor = status_sensor(entity)
        cards.append({
            "type": "entities", "title": label, "state_color": True,
            "entities": [
                {"entity": sensor, "name": "Status"},
                {"type": "attribute", "entity": sensor, "attribute": "online", "name": "Online"},
                {"type": "attribute", "entity": sensor, "attribute": "fps", "name": "FPS"},
                {"type": "attribute", "entity": sensor, "attribute": "confidence",
                 "name": "Confidence"},
                {"type": "attribute", "entity": sensor, "attribute": "last_detection",
                 "name": "Last detection"},
                {"entity": entity, "name": "HA camera entity"},
            ]})
    return {
        "title": "Cameras", "path": "cameras",
        "theme": "FiremeX", "type": "sections", "max_columns": 3,
        "badges": [{"type": "entity", "entity": status_sensor(e), "name": n}
                   for e, n in cameras],
        "sections": [
            {"type": "grid", "column_span": 2, "cards": cards},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Add a camera", "heading_style": "title",
                 "icon": "mdi:camera-plus"},
                {"type": "entities", "title": "Camera setup", "entities": [
                    {"type": "weblink", "url": "/config/integrations/dashboard",
                     "name": "Add camera integration", "icon": "mdi:camera-plus"},
                    {"type": "weblink", "url": "/config/entities",
                     "name": "Manage existing cameras", "icon": "mdi:cog"},
                ]},
            ]},
        ],
    }


def view_home_devices():
    """The Home Assistant devices FiremeX drives when an incident is declared."""
    return {
        "title": "Home Devices", "path": "home-devices",
        "theme": "FiremeX", "type": "sections", "max_columns": 3,
        "sections": [
            {"type": "grid", "column_span": 2, "cards": [
                {"type": "heading", "heading": "Devices FiremeX can drive",
                 "heading_style": "title", "icon": "mdi:home-lightning-bolt"},
                *_actuator_tiles(),
                {"type": "entities", "title": "Wiring", "entities": [
                    {"entity": "input_boolean.firemex_incident", "name": "Incident (the trigger)"},
                    {"entity": "input_boolean.fire_sprinklers", "name": "Sprinklers"},
                    {"entity": "input_boolean.evacuation_siren", "name": "Evacuation siren"},
                    {"entity": "input_boolean.fire_brigade_called", "name": "Fire brigade"}]},
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Automations", "heading_style": "title",
                 "icon": "mdi:robot"},
                {"type": "entities", "title": "Wiring these to real hardware", "entities": [
                    {"type": "weblink", "url": "/config/automation/dashboard",
                     "name": "Edit FiremeX automations", "icon": "mdi:robot"},
                    {"type": "weblink", "url": "/config/helpers",
                     "name": "Manage helpers", "icon": "mdi:tune"},
                ]},
            ]},
        ],
    }


def dashboard(cameras):
    """Views become tabs across the top of the dashboard — the horizontal
    equivalent of the deployed FiremeX sidebar (frontend/src/components/Sidebar.jsx).
    Cloud-only sections (Billing, Sites, Users, Support) are absent by design:
    this deployment has no accounts and no cloud."""
    return {"views": [
        view_dashboard(cameras),
        view_live_feed(cameras),
        view_alerts(cameras),
        view_incidents(cameras),
        view_cameras(cameras),
        view_home_devices(),
    ]}


async def provision(cameras):
    import websockets
    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        if json.loads(await ws.recv()).get("type") != "auth_ok":
            sys.exit("auth failed — check HA_TOKEN")

        # Home Assistant's helper-create commands do NOT deduplicate by name:
        # running this twice produced input_boolean.fire_sprinklers_2 and a
        # dashboard still wired to the originals. Check what exists first.
        _, all_states = rest("/states")
        existing = {st["entity_id"] for st in all_states}

        def already(domain: str, name: str) -> bool:
            return f"{domain}.{name.lower().replace(' ', '_')}" in existing

        counter = 0

        async def call(payload):
            nonlocal counter
            counter += 1
            await ws.send(json.dumps({"id": counter, **payload}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == counter:
                    return r

        print("helpers")
        for name, icon in BUTTONS:
            if already("input_button", name):
                print(f"  {name:30} already exists")
                continue
            r = await call({"type": "input_button/create", "name": name, "icon": icon})
            print(f"  {name:30} {'created' if r.get('success') else r.get('error')}")
        for name, icon in BOOLEANS:
            if already("input_boolean", name):
                print(f"  {name:30} already exists")
                continue
            r = await call({"type": "input_boolean/create", "name": name, "icon": icon})
            print(f"  {name:30} {'created' if r.get('success') else r.get('error')}")

        for _, label in cameras:
            name = confirm_button_name(label)
            if already("input_button", name):
                print(f"  {name:30} already exists")
                continue
            r = await call({"type": "input_button/create", "name": name,
                            "icon": "mdi:check-decagram"})
            print(f"  {name:30} {'created' if r.get('success') else r.get('error')}")

        pin_name = "FiremeX Pinned Camera"
        if already("input_select", pin_name):
            print(f"  {pin_name:30} already exists")
        else:
            r = await call({"type": "input_select/create", "name": pin_name, "icon": "mdi:pin",
                            "options": [PIN_ALL] + [label for _, label in cameras]})
            print(f"  {pin_name:30} {'created' if r.get('success') else r.get('error')}")

        print("dashboard")
        r = await call({"type": "lovelace/dashboards/create",
                        "url_path": "firemex-dashboard", "title": "FiremeX",
                        "icon": "mdi:fire-alert", "show_in_sidebar": True,
                        "require_admin": False})
        print(f"  create  {'ok' if r.get('success') else 'exists'}")
        r = await call({"type": "lovelace/config/save", "url_path": "firemex-dashboard",
                        "config": dashboard(cameras)})
        print(f"  views   {'ok' if r.get('success') else r.get('error')}")


def ensure_snapshot_placeholder(snapshot_dir: str, camera_entity: str) -> str:
    """A local_file camera refuses a path that does not exist yet, and on a
    fresh install no alert has fired, so write a placeholder frame first.

    It says so on its face rather than showing black: an operator glancing at
    the wall must never mistake "nothing has happened yet" for "the camera is
    dead".
    """
    import cv2
    import numpy as np

    os.makedirs(snapshot_dir, exist_ok=True)
    slug = camera_entity.split(".", 1)[-1]
    path = os.path.join(snapshot_dir, f"{slug}.jpg")
    if os.path.exists(path):
        return path

    frame = np.full((480, 640, 3), (16, 18, 20), np.uint8)
    cv2.putText(frame, "No detections yet", (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (150, 155, 165), 2, cv2.LINE_AA)
    cv2.putText(frame, slug.replace("_", " "), (120, 280),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 105, 115), 1, cv2.LINE_AA)
    cv2.imwrite(path, frame)
    return path


def ensure_snapshot_cameras(cameras, snapshot_dir: str, ha_config_dir: str = "/config"):
    """Register each camera's evidence frame as a local_file camera entity, so
    the dashboard can show a snapshot that refreshes as new alerts land.

    `ha_config_dir` is how Home Assistant sees its own config directory, which
    is not how the add-on sees it (the add-on gets it mapped at
    /homeassistant). The path handed to the config flow must be HA's view.
    """
    _, states = rest("/states")
    existing = {st["entity_id"] for st in states}

    for entity, label in cameras:
        slug = entity.split(".", 1)[-1]
        target = f"camera.firemex_snapshot_{slug}"
        if target in existing:
            print(f"  {target:44} already exists")
            continue

        ensure_snapshot_placeholder(snapshot_dir, entity)
        ha_path = f"{ha_config_dir.rstrip('/')}/www/firemex/{slug}.jpg"
        try:
            _, flow = rest("/config/config_entries/flow",
                           {"handler": "local_file", "show_advanced_options": False},
                           method="POST")
            _, result = rest(f"/config/config_entries/flow/{flow['flow_id']}",
                             {"name": f"FiremeX Snapshot {label}", "file_path": ha_path},
                             method="POST")
            ok = result.get("type") == "create_entry"
            print(f"  {target:44} {'created' if ok else result.get('reason') or result.get('errors')}")
        except Exception as exc:
            print(f"  {target:44} failed: {exc}")


def main(url: str | None = None, token: str | None = None,
         snapshot_dir: str | None = None, ha_config_dir: str = "/config"):
    configure(url, token)
    cameras = discover_cameras()
    if not cameras:
        raise SystemExit("No camera entities found in Home Assistant. Add a camera "
                         "integration first — FiremeX reads cameras from HA.")
    print(f"cameras found: {', '.join(label for _, label in cameras)}\n")

    print("automations")
    for aid, cfg in automations(cameras).items():
        status, _ = rest(f"/config/automation/config/{aid}", cfg, method="POST")
        print(f"  {aid:28} HTTP {status}")
    rest("/services/automation/reload", {}, method="POST")

    if snapshot_dir:
        print("snapshot cameras")
        ensure_snapshot_cameras(cameras, snapshot_dir, ha_config_dir)

    asyncio.run(provision(cameras))
    print("\nFiremeX dashboard provisioned.")
    return True


if __name__ == "__main__":
    main(snapshot_dir=os.environ.get("SNAPSHOT_DIR"),
         ha_config_dir=os.environ.get("HA_CONFIG_DIR", "/config"))
