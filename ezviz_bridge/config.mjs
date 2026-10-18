// Settings for the EZVIZ bridge.
//
// Inside the FiremeX add-on the bridge runs as an unprivileged user and gets
// everything it needs from its environment, set by ha_agent/ezviz.py:
//   BRIDGE_CONFIG_JSON   {app_key, app_secret, api, cameras, fps}
//   BRIDGE_USERNAME / BRIDGE_PASSWORD   credentials for its own HTTP server
// It reads no file in /data and never sees the Home Assistant token.
//
// On a development machine the settings come from ~/.firemex-ezviz.env (one
// camera) instead, so real keys never live in the repository.
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// "Loading Dock 2" -> "loading_dock_2". Used in URLs and Home Assistant names,
// so it must be stable and safe in a path. Same rule as ha_agent/ezviz.py.
export function slugify(name) {
  return String(name).toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'camera'
}

function readEnvFile(file) {
  const out = {}
  if (!fs.existsSync(file)) return out
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (m && m[2] !== '') out[m[1]] = m[2]
  }
  return out
}

export function loadConfig(env = process.env) {
  const fake = env.BRIDGE_FAKE === '1'
  const inAddon = Boolean(env.BRIDGE_CONFIG_JSON)
  let opts
  if (inAddon) {
    opts = JSON.parse(env.BRIDGE_CONFIG_JSON)
  } else {
    const e = { ...readEnvFile(env.EZVIZ_ENV_FILE || path.join(os.homedir(), '.firemex-ezviz.env')), ...env }
    opts = {
      app_key: e.EZVIZ_APP_KEY, app_secret: e.EZVIZ_APP_SECRET, api: e.EZVIZ_API,
      cameras: (e.EZVIZ_SERIAL || fake)
        ? [{ name: e.EZVIZ_NAME || 'EZVIZ Camera', serial: e.EZVIZ_SERIAL || 'FAKE00001',
             verify_code: e.EZVIZ_VERIFY_CODE || 'ABCDEF', channel: Number(e.EZVIZ_CHANNEL || 1) }]
        : [],
      fps: Number(e.BRIDGE_FPS || 2),
    }
  }

  const cameras = (opts.cameras || []).map((c) => ({
    name: c.name, id: slugify(c.name), serial: String(c.serial || '').trim().toUpperCase(),
    verifyCode: String(c.verify_code || '').trim(), channel: Number(c.channel || 1),
  }))
  const problems = []
  if (!fake && !opts.app_key) problems.push('ezviz_app_key is empty')
  if (!fake && !opts.app_secret) problems.push('ezviz_app_secret is empty')
  if (!cameras.length) problems.push('ezviz_cameras is empty')
  if (opts.bridge_password && String(opts.bridge_password).length < 12) problems.push('ezviz_bridge_password must be at least 12 characters')
  const seen = new Set()
  for (const c of cameras) {
    if (!c.name) problems.push('a camera has no name')
    if (!fake && !/^[A-Z0-9]{6,20}$/.test(c.serial)) problems.push(`${c.name}: serial "${c.serial}" does not look like an EZVIZ serial`)
    if (!fake && !c.verifyCode) problems.push(`${c.name}: verify_code is empty`)
    if (seen.has(c.id)) problems.push(`two cameras are both called "${c.name}"`)
    seen.add(c.id)
  }
  if (problems.length) {
    throw new Error('EZVIZ cameras are not set up: ' + problems.join('; ') +
      '. Fix it in the FiremeX Configuration tab (or ~/.firemex-ezviz.env).')
  }

  // In the add-on the credentials come from FiremeX (which gives the same ones
  // to Home Assistant); elsewhere they are new on every run.
  const auth = (env.BRIDGE_USERNAME && env.BRIDGE_PASSWORD)
    ? { username: env.BRIDGE_USERNAME, password: env.BRIDGE_PASSWORD }
    : { username: 'firemex', password: crypto.randomBytes(24).toString('base64url') }

  return {
    fake,
    appKey: opts.app_key, appSecret: opts.app_secret,
    api: String(opts.api || 'https://open.ezvizlife.com').replace(/\/$/, ''),
    cameras,
    fps: Math.min(Math.max(Number(opts.fps) || 2, 0.2), 5),
    hd: false,
    port: Number(env.BRIDGE_PORT || 8095),
    inAddon,
    // In the add-on Home Assistant reaches the bridge over the internal
    // network (no port is published on the host); elsewhere this machine only.
    listenHost: inAddon ? '0.0.0.0' : '127.0.0.1',
    auth,
    puppeteerPath: env.PUPPETEER_PATH || 'puppeteer-core',
    chromePath: env.CHROME_PATH || '',
    debug: env.BRIDGE_DEBUG === '1',
  }
}
