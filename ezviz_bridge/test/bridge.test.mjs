// node --test ezviz_bridge/test        (no camera, no EZVIZ account, no network)
import assert from 'node:assert/strict'
import test from 'node:test'

const { loadConfig, slugify } = await import('../config.mjs')
const { getToken, _resetTokenCache } = await import('../ezviz.mjs')

// As ha_agent/ezviz.py passes them: settings JSON + credentials in the env.
const good = {
  app_key: 'k', app_secret: 's',
  cameras: [{ name: 'Front Door', serial: 'bc1234567', verify_code: 'ABCDEF' }],
}
const addonEnv = (o, extra = {}) => ({
  BRIDGE_CONFIG_JSON: JSON.stringify(o), BRIDGE_USERNAME: 'firemex', BRIDGE_PASSWORD: 'p'.repeat(32), ...extra,
})

test('slugify makes stable, path-safe ids', () => {
  assert.equal(slugify('Front Door 2'), 'front_door_2')
  assert.equal(slugify('  Ünïcode / Gate  '), 'unicode_gate')
  assert.equal(slugify('!!!'), 'camera')
})

test('settings passed by FiremeX become cameras', () => {
  const cfg = loadConfig(addonEnv({ ...good, fps: 9 }))
  assert.equal(cfg.cameras[0].id, 'front_door')
  assert.equal(cfg.cameras[0].serial, 'BC1234567')            // upper-cased
  assert.equal(cfg.cameras[0].channel, 1)
  assert.equal(cfg.fps, 5)                                     // capped
  assert.deepEqual(cfg.auth, { username: 'firemex', password: 'p'.repeat(32) })
  assert.equal(cfg.listenHost, '0.0.0.0')                     // reachable by Home Assistant
})

test('missing keys are reported in plain words, all at once', () => {
  assert.throws(() => loadConfig(addonEnv({ app_key: '', app_secret: '', cameras: [{ name: 'Gate', serial: 'x', verify_code: '' }] })),
    (e) => /ezviz_app_key is empty/.test(e.message) && /ezviz_app_secret is empty/.test(e.message) &&
           /does not look like an EZVIZ serial/.test(e.message) && /verify_code is empty/.test(e.message))
})

test('two cameras with the same name are refused', () => {
  assert.throws(() => loadConfig(addonEnv({ ...good, cameras: [good.cameras[0], { ...good.cameras[0], serial: 'BC7654321' }] })),
    /both called/)
})

test('a chosen bridge password must be long enough', () => {
  assert.throws(() => loadConfig(addonEnv({ ...good, bridge_password: 'short' })), /at least 12 characters/)
})

test('off the add-on it listens on this machine only, with fresh credentials', () => {
  const a = loadConfig({ BRIDGE_FAKE: '1', EZVIZ_ENV_FILE: '/nonexistent' })
  const b = loadConfig({ BRIDGE_FAKE: '1', EZVIZ_ENV_FILE: '/nonexistent' })
  assert.equal(a.listenHost, '127.0.0.1')
  assert.notEqual(a.auth.password, b.auth.password)
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
