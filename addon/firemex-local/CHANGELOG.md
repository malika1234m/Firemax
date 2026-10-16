# Changelog

## 1.2.2

- **Quieter log.** Every still-image request was printed (two lines a second),
  which buried the HAZARD lines. Only FiremeX's own messages are logged now;
  a failed request still shows up as a warning.
- **Security profile (AppArmor).** The add-on can now write only to its own
  `/data`, the evidence folder in Home Assistant's config, and temporary
  folders. Its own code is read-only. Tested on Home Assistant OS 18.3: no
  blocked actions, detection unchanged.
- **Icon and logo** in the app store instead of the blank placeholder.
- Docs: install with one click from the README, and Home Assistant 2026.10's
  new names (Apps, App store).

## 1.2.1

- **Cameras now work on Home Assistant OS.** Inside HA OS the add-on reaches
  Home Assistant through the Supervisor's proxy, which waits for a response to
  finish before passing it on — so the live MJPEG camera stream never arrived
  and every camera was reported offline. Frames are now read as still images
  (`/api/camera_proxy`), at the `process_fps` rate detection already runs at.
- The camera-offline log line now says "no frame received yet" instead of
  "no frames for Nones" when a camera has never delivered a picture.

## 1.2.0

- **Licence key, and a free tier.** The add-on now installs and runs with no
  key at all, watching one camera so you can see it work on your own footage
  before paying for anything. A key from your FiremeX dashboard lifts the limit.
- The key is checked once and then cached in `/data`, so the add-on keeps
  working with no internet — the point of running it locally.
- Licensing never stops detection. If the licence server is unreachable the
  cached answer is honoured, and the worst outcome of any failure is the free
  tier: one camera still watched, never zero.
- The free tier watches the same camera on every restart (first by entity id),
  so a camera you believe is covered stays covered.

## 1.1.0

- **Sets itself up.** Installing the add-on and pressing Start now creates the
  FiremeX dashboard, helpers, automations and snapshot cameras. Previously this
  needed a script run by hand with a long-lived token.
- **Operator workflow.** Alerts are reviewed by a person and confirmed into an
  incident before anything actuates. One confirm button per camera, each beside
  that camera's evidence snapshot.
- **Evidence snapshots.** Every alert saves the annotated frame the model
  produced and republishes it as a camera entity, so an operator can see what
  was detected rather than only a confidence number.
- **Camera-offline alerts.** A camera that stops delivering frames raises its
  own alert, after a grace period so restarts do not cry wolf.
- **The alerting camera pins itself** on the Live Feed wall.
- **`hazard_classes` option**, defaulting to the learned classes (`fire`,
  `smoke`, `flame`). The colour and optical-flow branches misfire badly on Home
  Assistant's re-encoded camera proxy — measured at 10 false alerts in 14.
- **Six-tab dashboard**: Dashboard, Live Feed, Alerts, Incidents, Cameras,
  Home Devices.
- Fixed: a shared detector raced across camera pipelines and killed one
  camera's detection thread while it still reported itself online.
- Fixed: an automation reload or Home Assistant restart could declare an
  incident and turn on the sprinklers with nobody touching anything.

## 1.0.0

- First release. FiremeX as a fully local Home Assistant add-on.
- Cameras are read from Home Assistant's own camera entities — FiremeX never
  connects to a camera itself.
- Detection runs on this machine. No FiremeX account, no cloud, no internet
  required after the model is downloaded.
- Hazards are published as an event, a sensor, and the `firemax_hazard_alert`
  webhook, so existing FiremeX automations keep working.
- `sensor.firemex_hazard` returns to `clear` after a quiet period.
