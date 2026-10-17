# FiremeX EZVIZ Bridge

Makes **encrypted EZVIZ cameras** usable in Home Assistant, so FiremeX can watch
them for fire and smoke.

## Why it is needed

An EZVIZ camera with **Video Encryption** turned on only plays in EZVIZ's own
app: its video is locked with the camera's 6-letter **verification code**.
Home Assistant's built-in EZVIZ integration cannot show it (it needs encryption
off and RTSP on).

This add-on runs **EZVIZ's own player** — the same one EZVIZ provides to
developers — with your EZVIZ developer keys and each camera's verification code.
It turns the decrypted video into ordinary camera pictures and adds each camera
to Home Assistant. Nothing is hacked: it is EZVIZ's player, used with your own
keys and codes.

```
EZVIZ camera ─(encrypted)─► EZVIZ cloud ─► FiremeX EZVIZ Bridge ─► camera.<name> ─► FiremeX
                                            (EZVIZ player + code)
```

## What you need

1. **An EZVIZ Open Platform developer account** in the **same region** as your
   EZVIZ app account. In its console, open **Appkey management**: copy the
   **AppKey**, then press **Check** next to the AppSecret and copy it.
   The free trial covers 10 devices and 3 cameras streaming at once, for 120
   days. After that a paid plan is needed.
2. For each camera: its **serial number** and **verification code**, both on the
   sticker under the camera (also in the EZVIZ app under device information).
3. The camera **online in the EZVIZ app**.
4. **Internet.** The video comes through the EZVIZ cloud. If the internet is
   down, these cameras go offline (FiremeX raises a *camera offline* alert).

## Setup

1. Install this add-on from the FiremeX repository (Settings → Apps → Install
   app → FiremeX EZVIZ Bridge).
2. **Configuration** tab:
   - `app_key`, `app_secret` — from the EZVIZ developer console.
   - `cameras` — one entry per camera:
     ```yaml
     - name: Front Door
       serial: BC1234567
       verify_code: ABCDEF
     ```
3. **Save**, then **Start** on the Info tab.
4. Watch the **Log** tab. A healthy start looks like:
   ```
   bridge on :8095 — 1 camera(s)
   Front Door: playing — frames flowing
   Front Door: added to Home Assistant (camera.front_door)
   ```
5. Start (or restart) **FiremeX**. It finds `camera.front_door` within a minute.

## Problems

| Log says | What to do |
|---|---|
| `token request refused: 10017` / `10030` | AppKey or AppSecret is wrong — copy them again |
| `token request refused: 10005` | The AppKey is frozen — check the EZVIZ developer console |
| `player error … nErrorCode 5` | Wrong verification code for that camera |
| `no picture for 30 attempts` | Camera offline in the EZVIZ app, or the account region does not match the developer account |
| A bridged camera shows *unavailable* after reinstalling this add-on | Reinstalling creates new bridge credentials. Delete that MJPEG camera under Settings → Devices & services, then restart this add-on — it adds the camera again |
| `could not add to Home Assistant` | Add it by hand: Settings → Devices & services → Add integration → MJPEG IP Camera, with the addresses, username and password printed on the next log line (keep that line private) |

## Good to know

- **CPU:** each camera is decoded by a browser. A Raspberry Pi 4 manages about
  two cameras at the default 2 pictures per second.
- **Delay:** pictures arrive a few seconds behind real time (cloud round trip).
- **Privacy:** the verification codes stay in this add-on's settings; they are
  never sent to a dashboard or a browser you use.
- The add-on runs as root inside its own container, with Chromium's sandbox off
  (the container is the boundary), and opens no port on your network.
- The decrypted pictures are password-protected: the add-on creates its own
  credentials once and gives them to Home Assistant when it adds each camera,
  so other add-ons on the internal network cannot watch them.
- If you can, the simplest option is still to turn Video Encryption **off** and
  use Home Assistant's built-in EZVIZ integration — it works without internet.
