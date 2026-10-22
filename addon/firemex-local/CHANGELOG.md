# Changelog

## 1.4.0

- **A simpler dashboard.** Three tabs — Home, Emergency, History — instead of
  six. One line at the top says what is happening and what to do. While a
  camera alerts, the photo FiremeX reacted to and a single *Yes, it is a real
  fire* button appear beside its live picture, on one screen. Setup pages and
  tiles that showed "Entity not found" are gone.
- **Alerts on phones.** Alerts, offline cameras and incidents are also sent with
  `notify.notify`; install the Home Assistant app to receive them.
- **Stay safe guidance** on the Emergency tab, and the alert tells people not to
  go and look in person.
- Sprinkler, siren and fire-brigade controls open a window first, so a stray tap
  cannot set them off.
- Fixed: the orange-colour rule raised `fire` alerts although `hazard_classes`
  allowed only the trained model's classes. It now needs `colour_fire`.
- Fixed: a camera was reported offline after a 15-second gap, ignoring
  `camera_offline_after_seconds` (60). Short picture-fetch hiccups no longer
  raise offline alerts.
- Fixed: the "incident declared" notification read "unknown on unknown".
- Fixed: the free-tier warning was repeated in the log every minute.
- **A new fire model, trained on real photos** (D-Fire, about 21,000 images)
  instead of 169 computer-made ones. On a real room camera it catches more
  fires and mistakes fewer people for smoke.
- Fixed: when an update brought a new model, the add-on refused to start until
  the old one was deleted by hand. It now downloads the new model by itself.
- Cameras FiremeX does not watch are left off the dashboard.
- The Configuration tab now explains every option.

- **Encrypted EZVIZ cameras.** EZVIZ cameras with Video Encryption on only play
  in EZVIZ's own player, so Home Assistant could not show them. FiremeX can now
  run that official player for you, with your EZVIZ developer keys and each
  camera's verification code, and adds every camera to Home Assistant — where
  FiremeX watches it like any other. Set it up with the new `ezviz_` options;
  see the Documentation tab. Off unless `ezviz_cameras` is filled in.
- The bridge restarts by itself after any error, renews its EZVIZ token before
  it expires, and serves the decrypted pictures only inside Home Assistant,
  behind credentials it creates. Codes and passwords are never logged.
- Larger image: it now contains a headless browser (Chromium) for the EZVIZ
  player.

## 1.3.0

- **Licence keys are tied to installations.** Each Home Assistant that uses a
  key is recorded as an installation, and each plan allows a fixed number
  (Trial and Starter: 1, Pro: 5). A key passed to someone else stops working
  on the extra machine, which falls back to the free tier and says why in the
  log. The owner sees every installation under Settings > Add-on Licence Key
  and can remove one.
- **Licence answers are signed.** The add-on only accepts a licence answer
  carrying a valid signature from FiremeX, issued to this installation and not
  expired. Editing the cached licence file, copying it to another machine, or
  using a home-made licence server no longer unlocks anything.
- The licence is re-checked daily while running, so a cancelled subscription
  or a removed installation takes effect without a restart.
- Unchanged: with no key, an invalid key or no internet, FiremeX still watches
  one camera. A licence problem never stops detection completely. A valid
  licence keeps working offline for up to 60 days.
- Add-ons older than 1.3.0 can no longer use a paid licence: update to keep it.

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
