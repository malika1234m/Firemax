# Changelog

## 0.1.0

- First version. Plays encrypted EZVIZ cameras with EZVIZ's own web player
  (EZUIKit) and the camera's verification code, and serves each one as an
  MJPEG camera (`/<camera>/stream.mjpg`, `/<camera>/snapshot.jpg`).
- Adds each camera to Home Assistant automatically (MJPEG IP Camera), so
  FiremeX picks it up like any other camera.
- Recovers on its own: the player restarts after any error, with a growing
  pause, and the EZVIZ token is renewed before it expires.
