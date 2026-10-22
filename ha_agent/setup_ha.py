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
import sys
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

def _tell_phones(title, message):
    """Also send the alert to phones (the Home Assistant app), so nobody misses
    a fire because they were not looking at the screen. Always the LAST action
    and allowed to fail: with no phone set up it must never stop the response."""
    return {"service": "notify.notify", "continue_on_error": True, "data": {
        "title": title, "message": message,
        "data": {"tag": "firemex", "url": "/firemex-dashboard/dashboard",
                 "clickAction": "/firemex-dashboard/dashboard"}}}


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
            _tell_phones("FIRE — incident declared",
                         "Confirmed on {{ cam }}. Get everyone out by the nearest exit."),
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
                            "Open the FiremeX dashboard and confirm before declaring an incident.")}},
                       _tell_phones("FiremeX — possible {{ trigger.event.data.hazard_type }}",
                                    "{{ trigger.event.data.camera_name }}: look at the photo in "
                                    "FiremeX and confirm if it is real.")],
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
                            "frames and is no longer being monitored.")}},
                       _tell_phones("FiremeX — camera offline",
                                    "{{ trigger.event.data.camera_name }} is not sending pictures. "
                                    "Check its power and Wi-Fi.")],
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
                                "{{ state_attr('sensor.firemex_hazard', 'camera_name') or 'no camera' }} "
                                "({{ state_attr('sensor.firemex_hazard', 'confidence') or 'declared by hand' }}).")}},
                _tell_phones("FIRE — incident declared",
                             "Declared by the operator. Get everyone out by the nearest exit."),
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
#
# Written for someone who has never seen Home Assistant: three tabs, one plain
# sentence at the top saying what is happening and what to do, red only when
# something is actually wrong. Setup (adding cameras, wiring devices) lives in
# Home Assistant's own Settings, not on the screen people watch.

INCIDENT = "input_boolean.firemex_incident"
STAND_DOWN = "input_button.firemex_stand_down"
# Two columns: wide enough to read on a laptop, and it folds to one on a phone.
COLUMNS = 2


def _section(cards, span=1):
    """A grid section. Inside a wide one Home Assistant would set cards side by
    side; stacking them full width keeps the picture, its status and its button
    reading top to bottom."""
    if span > 1:
        cards = [c if c["type"] == "heading" else {**c, "grid_options": {"columns": "full"}}
                 for c in cards]
    return {"type": "grid", "column_span": span, "cards": cards}


def _when(entity, card, state=None, state_not=None):
    cond = {"condition": "state", "entity": entity}
    cond.update({"state": state} if state is not None else {"state_not": state_not})
    return {"type": "conditional", "conditions": [cond], "card": card}


def _status_banner(cameras):
    """The one line everybody reads: what is happening, and what to do."""
    sensors = [status_sensor(e) for e, _ in cameras]
    return {"type": "markdown", "text_only": True, "content": (
        "{% set h = states('sensor.firemex_hazard') %}"
        f"{{% set cams = {sensors} %}}"
        "{% set offline = cams | select('is_state', 'camera_offline') | list %}"
        f"{{% if is_state('{INCIDENT}', 'on') %}}"
        '<ha-alert alert-type="error" title="Incident declared — fire response is running">'
        "Get everyone out. Open the <b>Emergency</b> tab for the sprinklers, siren and "
        "fire brigade. When everyone is safe, press <b>All safe — end the incident</b>."
        "</ha-alert>"
        "{% elif h not in ['clear', 'unknown', 'unavailable'] %}"
        '<ha-alert alert-type="warning" title="Possible {{ h }} on '
        "{{ state_attr('sensor.firemex_hazard', 'camera_name') }} "
        "({{ state_attr('sensor.firemex_hazard', 'confidence') }} sure)\">"
        "Look at the photo. If it is a real fire, press <b>Yes, it is a real fire</b>. "
        "If it is not, do nothing — the alert clears by itself. "
        "Do not go to check it in person: the photo is safer."
        "</ha-alert>"
        "{% elif offline %}"
        '<ha-alert alert-type="warning" title="A camera is offline">'
        "{{ offline | map('state_attr', 'camera_name') | join(', ') }} is not sending "
        "pictures, so FiremeX cannot watch it. Check its power and Wi-Fi."
        "</ha-alert>"
        "{% else %}"
        '<ha-alert alert-type="success" title="All clear"></ha-alert>'
        "{% endif %}")}


def _camera_sections(entity, label):
    """Two half-width sections side by side: the live picture with its status,
    and — only while it is alerting — the evidence photo with the one button
    that matters. Side by side, both fit on one screen with no scrolling."""
    sensor = status_sensor(entity)
    alerting = {"condition": "and", "conditions": [
        {"condition": "state", "entity": sensor, "state_not": "clear"},
        {"condition": "state", "entity": sensor, "state_not": "camera_offline"},
        {"condition": "state", "entity": INCIDENT, "state": "off"}]}
    live = _section([
        {"type": "heading", "heading": label, "heading_style": "title", "icon": "mdi:cctv"},
        {"type": "markdown", "text_only": True, "content": (
            f"{{% set s = states('{sensor}') %}}"
            "{% if s == 'clear' %}<ha-icon icon=\"mdi:check-circle\"></ha-icon> No fire seen"
            "{% elif s == 'camera_offline' %}<ha-icon icon=\"mdi:cctv-off\"></ha-icon> "
            "Not sending pictures — check its power and Wi-Fi"
            "{% elif s in ['unknown', 'unavailable'] %}<ha-icon icon=\"mdi:timer-sand\"></ha-icon> Starting up…"
            "{% else %}<ha-icon icon=\"mdi:fire-alert\"></ha-icon> <b>Possible {{ s }}</b> — "
            f"{{{{ state_attr('{sensor}', 'confidence') }}}} sure{{% endif %}}")},
        # Stills, not "live": this camera streams H.265, which browsers cannot
        # play, so a live view is just a black box.
        {"type": "picture-entity", "entity": entity, "camera_view": "auto",
         "show_name": False, "show_state": False},
    ])
    evidence = _section([
        {"type": "conditional", "conditions": [alerting], "card": {
            "type": "heading", "heading": "Is this a real fire?", "heading_style": "title",
            "icon": "mdi:fire-alert"}},
        {"type": "conditional", "conditions": [alerting], "card": {
            "type": "picture-entity", "entity": snapshot_camera(entity),
            "name": "What FiremeX saw", "show_state": False}},
        {"type": "conditional", "conditions": [alerting], "card": {
            "type": "tile", "entity": confirm_button(label),
            "name": "Yes, it is a real fire", "icon": "mdi:fire-alert", "color": "red", "hide_state": True,
            "tap_action": {"action": "toggle"}}},
    ])
    return [live, evidence]


def _actuator_tiles():
    # Opening the dialog first means a stray tap cannot start the sprinklers.
    deliberate = {"tap_action": {"action": "more-info"},
                  "icon_tap_action": {"action": "more-info"}}
    return [
        {"type": "tile", "entity": "input_boolean.fire_sprinklers",
         "name": "Sprinklers", "icon": "mdi:sprinkler-fire", **deliberate},
        {"type": "tile", "entity": "input_boolean.evacuation_siren",
         "name": "Evacuation siren", "icon": "mdi:bullhorn", **deliberate},
        {"type": "tile", "entity": "input_boolean.fire_brigade_called",
         "name": "Fire brigade", "icon": "mdi:fire-truck", **deliberate},
    ]


def view_dashboard(cameras):
    return {
        "title": "Home", "path": "dashboard",
        "theme": "FiremeX", "type": "sections", "max_columns": COLUMNS,
        "sections": [
            _section([
                _status_banner(cameras),
                _when(INCIDENT, {"type": "tile", "entity": STAND_DOWN,
                                 "name": "All safe — end the incident",
                                 "icon": "mdi:check-circle-outline", "color": "green", "hide_state": True,
                                 "tap_action": {"action": "toggle"}}, state="on"),
            ], COLUMNS),
            *[sec for e, n in cameras for sec in _camera_sections(e, n)],
        ],
    }


def view_emergency(cameras):
    return {
        "title": "Emergency", "path": "emergency",
        "theme": "FiremeX", "type": "sections", "max_columns": COLUMNS,
        "sections": [
            _section([_status_banner(cameras)], COLUMNS),
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Building response", "heading_style": "title",
                 "icon": "mdi:home-lightning-bolt"},
                *_actuator_tiles(),
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Stay safe", "heading_style": "title",
                 "icon": "mdi:shield-alert"},
                {"type": "markdown", "text_only": True, "content": (
                    "1. Get everyone out by the **nearest exit**. Do not use lifts.\n"
                    "2. Do not try to put out a large fire. Use an extinguisher only on a "
                    "small fire, with your exit behind you.\n"
                    "3. Call the fire brigade, then meet at the assembly point.\n"
                    "4. Do not go back inside until the fire brigade says it is safe.")},
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": "Incident", "heading_style": "title",
                 "icon": "mdi:alert-octagon"},
                _when(INCIDENT, {"type": "tile", "entity": STAND_DOWN,
                                 "name": "All safe — end the incident",
                                 "icon": "mdi:check-circle-outline", "color": "green", "hide_state": True,
                                 "tap_action": {"action": "toggle"}}, state="on"),
                _when(INCIDENT, {"type": "tile",
                                 "entity": "input_button.firemex_declare_incident",
                                 "name": "Declare a fire I can see myself",
                                 "icon": "mdi:fire-alert", "color": "red", "hide_state": True,
                                 "tap_action": {"action": "toggle"}}, state="off"),
            ]},
        ],
    }


def view_history(cameras):
    return {
        "title": "History", "path": "history",
        "theme": "FiremeX", "type": "sections", "max_columns": COLUMNS,
        "sections": [_section([
            {"type": "heading", "heading": "Last 24 hours", "heading_style": "title",
             "icon": "mdi:history"},
            {"type": "logbook", "hours_to_show": 24, "entities": [
                INCIDENT, "input_boolean.fire_sprinklers",
                "input_boolean.evacuation_siren", "input_boolean.fire_brigade_called",
                *[status_sensor(e) for e, _ in cameras]]},
        ], COLUMNS)],
    }


def dashboard(cameras):
    """Views become tabs across the top of the dashboard."""
    return {"views": [view_dashboard(cameras), view_emergency(cameras), view_history(cameras)]}


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
        # Ask first: creating one that exists logs an ERROR in Home Assistant
        # on every add-on start, which makes a healthy system look broken.
        listed = await call({"type": "lovelace/dashboards/list"})
        if any(d.get("url_path") == "firemex-dashboard" for d in listed.get("result") or []):
            print("  create  exists")
        else:
            r = await call({"type": "lovelace/dashboards/create",
                            "url_path": "firemex-dashboard", "title": "FiremeX",
                            "icon": "mdi:fire-alert", "show_in_sidebar": True,
                            "require_admin": False})
            print(f"  create  {'ok' if r.get('success') else r.get('error')}")
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


def cameras_to_show(cameras, only):
    """Cameras FiremeX does not watch (free tier, or excluded in the options)
    would only show up as "offline" and confuse whoever is looking."""
    return cameras if only is None else [c for c in cameras if c[0] in only]


def main(url: str | None = None, token: str | None = None,
         snapshot_dir: str | None = None, ha_config_dir: str = "/config", only=None):
    configure(url, token)
    cameras = cameras_to_show(discover_cameras(), only)
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
