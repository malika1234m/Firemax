# FiremeX Fire & Smoke Detection (Local)

Detects fire and smoke in the cameras you **already have in Home Assistant**.
Everything runs on this machine: no FiremeX account, no cloud, and no internet
connection once the model has been downloaded.

## How it works

```
Your cameras ──► Home Assistant ──► FiremeX ──► your automations
  (Hikvision, ONVIF,      (owns the         (runs the      (sirens, lights,
   generic RTSP…)          connection)       model here)     notifications)
```

FiremeX never connects to your cameras itself. Whichever integration already
provides them has done that work; FiremeX reads those feeds through Home
Assistant. So there are no camera URLs or passwords to enter a second time, and
nothing new is exposed on your network.

## Setup

1. Make sure your cameras appear in Home Assistant as `camera.*` entities.
2. Install this add-on and press **Start**. That is the whole setup — every
   camera entity is watched by default.
3. Watch the **Log** tab — type `HAZARD` in its search box to see only the
   alerts. A healthy start looks like:

```
FiremeX Home Assistant add-on v1.0.0 — fully local
model verified: /data/fire_model.pt
Detector: YOLO (real model)
camera added: Warehouse Bay (camera.warehouse_bay)
watching 1 camera(s)
```

Cameras added to Home Assistant later are picked up within a minute — no
restart needed.

## The operator workflow

FiremeX raises **alerts**. Only a person declares an **incident**.

```
detection -> alert (with evidence snapshot) -> operator reviews -> CONFIRM -> automations
```

Nothing actuates on a detection. Sprinklers, sirens and any call-out hang off
`input_boolean.firemex_incident`, which only an operator's confirm button turns
on. The model is confident and sometimes wrong, and a false sprinkler discharge
is its own emergency.

`ha_agent/setup_ha.py` provisions the whole workflow — helpers, automations and
a six-tab dashboard (Dashboard / Live Feed / Alerts / Incidents / Cameras /
Home Devices):

```bash
HA_URL=http://homeassistant.local:8123 HA_TOKEN=<long-lived token> \
    python ha_agent/setup_ha.py
```

**Evidence snapshots.** Every alert saves the annotated frame the model produced
— the boxes and confidences it actually drew — to `www/firemex/<camera>.jpg`,
republished as a `local_file` camera. The Alerts tab shows it beside that
camera's confirm button. A confidence number alone is not something a person can
confirm or reject; the picture is.

**One confirm button per camera**, because the evidence being confirmed belongs
to a camera. There is also a "Declare without a camera" button for when an
operator sees a fire themselves.

**The alerting camera pins itself** on the Live Feed wall, so a crew watching
several cameras does not have to hunt for the one that fired.

**Camera-offline alerts.** A camera that stops delivering frames raises its own
alert. Silence from a camera is indistinguishable from safety, which is the one
mistake a fire system must never make.

## What it gives you

When a hazard is detected, FiremeX announces it three ways, so you can build an
automation whichever way you prefer:

| | What |
|---|---|
| **Event** | `firemex_hazard` — the idiomatic automation trigger |
| **Sensor** | `sensor.firemex_hazard` — state is the hazard type, or `clear` |
| **Webhook** | `firemax_hazard_alert` — so the `ha_automation.yaml` in this repository works unchanged |

All three carry `hazard_type`, `camera_name`, `confidence`, `entity_id` and
`timestamp`.

A minimal automation:

```yaml
automation:
  - alias: "FiremeX — fire detected"
    trigger:
      - platform: event
        event_type: firemex_hazard
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.hazard_type in ['fire', 'smoke', 'flame'] }}"
    action:
      - service: notify.notify
        data:
          message: >
            {{ trigger.event.data.hazard_type | upper }} at
            {{ trigger.event.data.camera_name }}
            ({{ (trigger.event.data.confidence * 100) | int }}%)
```

`sensor.firemex_hazard` returns to `clear` once nothing has been detected for
`clear_after_seconds`, so it is safe to use in template conditions.

## Licensing

FiremeX is free for **one camera**. Install it, press Start, and it watches a
single camera with no account and no key — enough to see it work on your own
footage.

To watch every camera, paste your licence key into the `licence_key` option.
You will find it in the FiremeX dashboard under **Get Started → Add your
licence key**.

The key is checked against the FiremeX cloud and the signed answer is cached in
`/data`, so the add-on keeps running with no internet for up to 60 days. It is
re-checked daily while running. If the licence server is ever unreachable, the
cached answer is used — and if it cannot be resolved at all, the add-on drops to
the free tier rather than stopping. It is a fire detector; it does not stop
watching your building because a subscription server is down.

Each Home Assistant using your key counts as one **installation**, and your plan
allows a fixed number (Trial and Starter: 1, Pro: 5). You can see and remove
installations in the dashboard under **Settings → Add-on Licence Key**. If the
log says the licence is *already active* on another installation, remove the old
one there — for example after reinstalling Home Assistant.

## EZVIZ cameras

FiremeX watches any camera Home Assistant has. EZVIZ cameras come in two ways:

**Video Encryption off** (simplest, works without internet): in the EZVIZ app
turn on RTSP (Settings → LAN Live View → your camera → Local Server Settings),
then add Home Assistant's built-in **EZVIZ** integration. FiremeX finds the
camera like any other.

**Video Encryption on**: Home Assistant cannot show these at all — the video is
locked with the camera's 6-letter verification code and only plays in EZVIZ's
own player. FiremeX can run that player for you:

```
EZVIZ camera ─(encrypted)─► EZVIZ cloud ─► FiremeX (EZVIZ's own player + your code)
                                         ─► camera.<name> in Home Assistant ─► FiremeX detection
```

Nothing is hacked: it is EZVIZ's official player, used with your own EZVIZ
developer keys and your cameras' verification codes.

**You need**

1. An **EZVIZ Open Platform developer account** in the **same region** as your
   EZVIZ app account. In its console open **Appkey management**, copy the
   **AppKey**, press **Check** and copy the **AppSecret**. The free trial covers
   10 devices and 3 cameras streaming at once for 120 days; then a paid plan.
2. Each camera's **serial number** and **verification code** — on the sticker
   under the camera, and in the EZVIZ app under device information.
3. The camera **online in the EZVIZ app**, and **internet** for this machine:
   the video comes through the EZVIZ cloud. If the internet drops, FiremeX
   raises a *camera offline* alert for these cameras.

**Setup** — in this add-on's **Configuration** tab:

```yaml
ezviz_app_key: <AppKey>
ezviz_app_secret: <AppSecret>
ezviz_cameras:
  - name: Front Door
    serial: BC1234567
    verify_code: ABCDEF
```

Save. The add-on restarts, and the Log shows:

```
EZVIZ: starting the bridge for 1 camera(s)
Front Door: playing — frames flowing
Front Door: added to Home Assistant (camera.front_door)
```

Within a minute FiremeX starts watching `camera.front_door`. If you limit
detection with the `cameras` option, add `camera.front_door` to that list.

**If something is wrong**

| Log says | What to do |
|---|---|
| `EZVIZ token request refused: 10017` / `10030` | AppKey or AppSecret is wrong — copy them again |
| `EZVIZ token request refused: 10005` | The AppKey is frozen — check the EZVIZ developer console |
| `player error … nErrorCode 5` | Wrong verification code for that camera |
| `no picture for 30 attempts` | Camera offline in the EZVIZ app, or the account region does not match the developer account |
| `EZVIZ cameras are not set up: …` | The line says which setting is missing; fix it and save |
| `could not add to Home Assistant` | Set `ezviz_bridge_password` (12+ characters), save, then add it by hand: Settings → Devices & services → Add integration → MJPEG IP Camera, with the addresses and username from the next log line and that password |
| An EZVIZ camera shows *unavailable* after reinstalling FiremeX | Reinstalling creates new internal credentials: delete that MJPEG camera under Settings → Devices & services and restart FiremeX — it is added again |

**Good to know**

- **CPU:** each EZVIZ camera is decoded by a browser inside the add-on. A
  Raspberry Pi 4 manages about two at the default 2 pictures per second.
- **Delay:** pictures arrive a few seconds behind real time (cloud round trip).
- **Privacy:** verification codes stay in this add-on's settings and are never
  sent to a dashboard or browser. The decrypted pictures are only served inside
  Home Assistant's internal network, behind credentials the add-on creates and
  gives to Home Assistant; no port is opened on your network.

## Options

| Option | What it does |
|---|---|
| `licence_key` | Your key from the FiremeX dashboard. **Leave blank to run the free tier** — one camera, no account. See Licensing above. |
| `cameras` | Which camera entities to watch. **Empty means all of them.** Naming entities explicitly is how you keep the model off cameras that don't matter — a doorbell costs CPU and false alarms, not safety. |
| `confidence_threshold` | How confident a detection must be to raise a hazard. Lower catches more and cries wolf more. |
| `alert_cooldown_seconds` | Minimum gap between hazards from the same camera. Stops one fire producing hundreds of notifications. |
| `detector_mode` | `yolo` for real detection. `mock` runs everything except the model — use it to confirm the add-on sees your cameras before committing a Pi to inference. |
| `model_url` / `model_sha256` | Where the weights come from and how they're verified. **Leave the checksum set** — a swapped or corrupted model is a silent detection failure. |
| `process_fps` | How often each camera is analysed. Default 2. Raise it only if this machine has capacity to spare. |
| `clear_after_seconds` | Quiet period before the sensor returns to `clear`. |
| `camera_offline_after_seconds` | Grace period before a silent camera raises an offline alert. Stops every restart crying wolf. |
| `save_snapshots` | Keep the annotated evidence frame for each alert. Leave on — it is what an operator reviews. |
| `hazard_classes` | **Which classes may raise an alert.** Defaults to `fire`, `smoke`, `flame` — see below. |

### Why `hazard_classes` defaults to the learned classes only

FiremeX also detects gas fires by flame colour and gas leaks by heat shimmer,
with no training data — deterministic branches that are the interesting half of
the detector. But Home Assistant's camera proxy **re-encodes every frame**, and
that compression noise reads as heat shimmer while blue sky and pale smoke read
as a gas flame. Measured on ordinary footage through the proxy, they fired
continuously at 82–95%: 10 of 14 alerts were false.

An operator console that cries wolf is worse than one with fewer features —
people stop reading it, and then the real alert is missed too. Add
`gas_fire`, `lpg_fire`, `chemical_fire`, `gas_shimmer` or `person_down` once you
have tested them against your own cameras.

## Hardware

Detection is real computer vision. **4 GB RAM is a sensible floor**, and each
camera costs CPU continuously. On a Raspberry Pi, watch two or three cameras at
`process_fps: 1`, not ten.

Start with `detector_mode: mock` to confirm the wiring, then switch to `yolo`.

## Important: this is not a monitored alarm system

FiremeX raises hazards; it does not judge them. In the cloud product a human
operator confirms a detection before sirens sound or authorities are called.
Here, **your automation is that judgement** — so think about what it triggers.

The model is far better at `fire` and `smoke` than at the colour-rule gas
classes, which can misfire on blue sky and pale smoke. The example automations
deliberately filter to `fire`, `smoke` and `flame` for this reason. Widen that
list only if you have tested it against your own cameras.

## Troubleshooting

**"No Home Assistant camera entities to watch yet"** — Home Assistant has no
`camera.*` entities, or the ones named in `cameras` don't exist. Check
**Developer Tools → States** and filter for `camera.`.

**"configured camera '…' is not an available Home Assistant camera entity"** —
a typo in `cameras`, or that camera is currently `unavailable` in HA.

**"No SUPERVISOR_TOKEN"** — the add-on isn't running under the Supervisor.
This can only run on Home Assistant OS or Supervised.

**Stream keeps reconnecting** — Home Assistant can't reach that camera either.
Open the camera in the HA dashboard; if it's broken there, fix it there.

**High CPU** — lower `process_fps`, or list fewer cameras in `cameras`.
