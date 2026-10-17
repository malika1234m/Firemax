// node --test ezviz_bridge/test        (no camera, no EZVIZ account, no network)
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ezviz-bridge-'))
process.env.OPTIONS_PATH = path.join(tmp, 'options.json')
const { loadConfig, slugify } = await import('../config.mjs')
const { getToken, _resetTokenCache } = await import('../ezviz.mjs')
const { registerCamera, cameraUrls } = await import('../homeassistant.mjs')

const writeOptions = (o) => fs.writeFileSync(process.env.OPTIONS_PATH, JSON.stringify(o))
const good = {
  app_key: 'k', app_secret: 's', cameras: [{ name: 'Front Door', serial: 'bc1234567', verify_code: 'ABCDEF' }],
}

test('slugify makes stable, path-safe ids', () => {
  assert.equal(slugify('Front Door 2'), 'front_door_2')
  assert.equal(slugify('  Ünïcode / Gate  '), 'unicode_gate')
  assert.equal(slugify('!!!'), 'camera')
})

test('add-on options become cameras', () => {
  writeOptions({ ...good, fps: 9 })
  const cfg = loadConfig({})
  assert.equal(cfg.cameras[0].id, 'front_door')
  assert.equal(cfg.cameras[0].serial, 'BC1234567')            // upper-cased
  assert.equal(cfg.cameras[0].channel, 1)
  assert.equal(cfg.fps, 5)                                     // capped
  assert.equal(cfg.registerInHA, false)                        // no SUPERVISOR_TOKEN here
})

test('missing keys are reported in plain words, all at once', () => {
  writeOptions({ app_key: '', app_secret: '', cameras: [{ name: 'Gate', serial: 'x', verify_code: '' }] })
  assert.throws(() => loadConfig({}), (e) =>
    /app_key is empty/.test(e.message) && /app_secret is empty/.test(e.message) &&
    /does not look like an EZVIZ serial/.test(e.message) && /verify_code is empty/.test(e.message))
})

test('two cameras with the same name are refused', () => {
  writeOptions({ ...good, cameras: [good.cameras[0], { ...good.cameras[0], serial: 'BC7654321' }] })
  assert.throws(() => loadConfig({}), /both called/)
})

test('token: success keeps the regional server, refusals are explained', async () => {
  _resetTokenCache()
  const ok = async () => ({ json: async () => ({ code: '200', data: {
    accessToken: 'at', expireTime: Date.now() + 7 * 864e5, areaDomain: 'https://isgpopen.ezvizlife.com' } }) })
  const t = await getToken({ api: 'https://open.ezvizlife.com', appKey: 'k', appSecret: 's' }, ok)
  assert.equal(t.accessToken, 'at')
  assert.equal(t.domain, 'https://isgpopen.ezvizlife.com')

  _resetTokenCache()
  const bad = async () => ({ json: async () => ({ code: '10030', msg: 'appKey and appSecret mismatch' }) })
  await assert.rejects(getToken({ api: 'x', appKey: 'k2', appSecret: 's' }, bad), /10030/)
})

function fakeHA(existing = []) {
  const calls = []
  const impl = async (url, init = {}) => {
    calls.push({ url, method: init.method || 'GET', body: init.body && JSON.parse(init.body) })
    if (url.endsWith('/config/config_entries/entry')) return { ok: true, json: async () => existing }
    if (url.endsWith('/config/config_entries/flow')) return { ok: true, json: async () => ({ flow_id: 'f1' }) }
    if (url.endsWith('/config/config_entries/flow/f1')) return { ok: true, json: async () => ({ type: 'create_entry' }) }
    return { ok: false, status: 404, json: async () => ({}) }
  }
  return { impl, calls }
}

test('a camera is added to Home Assistant through the MJPEG config flow', async () => {
  const { impl, calls } = fakeHA()
  const cam = { id: 'front_door', name: 'Front Door' }
  assert.equal(await registerCamera(cam, 8095, impl), 'added to Home Assistant')
  const submit = calls.find((c) => c.url.endsWith('/flow/f1')).body
  assert.equal(submit.name, 'Front Door')
  assert.match(submit.mjpeg_url, /:8095\/front_door\/stream\.mjpg$/)
  assert.match(submit.still_image_url, /:8095\/front_door\/snapshot\.jpg$/)
  assert.equal(calls.find((c) => c.url.endsWith('/flow')).body.handler, 'mjpeg')
})

test('a camera already in Home Assistant is not added twice', async () => {
  const { impl, calls } = fakeHA([{ domain: 'mjpeg', title: 'Front Door' }])
  assert.equal(await registerCamera({ id: 'front_door', name: 'Front Door' }, 8095, impl), 'already in Home Assistant')
  assert.equal(calls.length, 1)                                // only the lookup
})

test('camera URLs use the add-on hostname Home Assistant can reach', () => {
  const u = cameraUrls({ id: 'gate' }, 'bd0c1f44-firemex-ezviz-bridge', 8095)
  assert.equal(u.mjpeg_url, 'http://bd0c1f44-firemex-ezviz-bridge:8095/gate/stream.mjpg')
})
