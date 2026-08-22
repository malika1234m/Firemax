# Changelog

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
