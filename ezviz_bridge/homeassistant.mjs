// Adds each bridged EZVIZ camera to Home Assistant as an "MJPEG IP Camera",
// through Home Assistant's own config flow — exactly what a user would do in
// Settings > Devices & services > Add integration, but without them having to.
// FiremeX then finds the new camera.* entity like any other camera.
//
// As an add-on with `homeassistant_api: true` the bridge has SUPERVISOR_TOKEN
// and reaches Core at http://supervisor/core/api. Home Assistant reaches the
// bridge back by the add-on's hostname on the internal network.
import os from 'node:os'

const API = (process.env.HA_API_URL || 'http://supervisor/core/api').replace(/\/$/, '')
const log = (...a) => console.log(new Date().toISOString(), ...a)

async function ha(pathname, init = {}, fetchImpl = fetch) {
  const res = await fetchImpl(API + pathname, {
    ...init,
    headers: { Authorization: `Bearer ${process.env.SUPERVISOR_TOKEN}`, 'Content-Type': 'application/json',
               ...(init.headers || {}) },
  })
  if (!res.ok) throw new Error(`${init.method || 'GET'} ${pathname} -> HTTP ${res.status}`)
  return res.json()
}

export function cameraUrls(cam, host = os.hostname(), port = 8095) {
  return {
    mjpeg_url: `http://${host}:${port}/${cam.id}/stream.mjpg`,
    still_image_url: `http://${host}:${port}/${cam.id}/snapshot.jpg`,
  }
}

// One camera. Home Assistant's MJPEG flow tests the address before saving, so
// this is only called once the bridge has a picture to show it.
export async function registerCamera(cam, port, auth, fetchImpl = fetch) {
  const urls = cameraUrls(cam, os.hostname(), port)
  const entries = await ha('/config/config_entries/entry', {}, fetchImpl)
  if (entries.some((e) => e.domain === 'mjpeg' && e.title === cam.name)) {
    return 'already in Home Assistant'
  }
  const flow = await ha('/config/config_entries/flow', {
    method: 'POST', body: JSON.stringify({ handler: 'mjpeg', show_advanced_options: false }),
  }, fetchImpl)
  const result = await ha(`/config/config_entries/flow/${flow.flow_id}`, {
    method: 'POST',
    body: JSON.stringify({ name: cam.name, ...urls, username: auth.username, password: auth.password,
                           verify_ssl: false }),
  }, fetchImpl)
  if (result.type === 'create_entry') return 'added to Home Assistant'
  if (result.type === 'abort' && result.reason === 'already_configured') return 'already in Home Assistant'
  throw new Error(`Home Assistant refused ${cam.name}: ${JSON.stringify(result.errors || result.reason)}`)
}

export async function registerCameras(cfg, cams) {
  for (const cam of cams) {
    (async () => {
      // Wait (up to an hour) for the first decoded picture.
      for (let i = 0; i < 720 && !cam.latest; i++) await new Promise((r) => setTimeout(r, 5000))
      if (!cam.latest) return log(`${cam.name}: no picture yet, so not added to Home Assistant`)
      try {
        log(`${cam.name}: ${await registerCamera(cam, cfg.port, cfg.auth)} (camera.${cam.id})`)
      } catch (e) {
        // Give everything needed to add it by hand. The add-on log is only
        // visible to Home Assistant administrators; keep it out of screenshots.
        const u = cameraUrls(cam, os.hostname(), cfg.port)
        log(`${cam.name}: could not add to Home Assistant: ${e.message}`)
        log(`  add it by hand (MJPEG IP Camera): MJPEG URL ${u.mjpeg_url}  still image URL ` +
            `${u.still_image_url}  username ${cfg.auth.username}  password ${cfg.auth.password}  (keep private)`)
      }
    })()
  }
}
