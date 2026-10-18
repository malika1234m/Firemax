// Settings for the EZVIZ bridge.
//
// As a Home Assistant add-on they come from /data/options.json, which the
// Supervisor writes from the add-on's Configuration tab. On a development
// machine they come from ~/.firemex-ezviz.env (a single camera), so real keys
// never have to live in the repository.
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

export const OPTIONS_PATH = process.env.OPTIONS_PATH || '/data/options.json'

// "Loading Dock 2" -> "loading_dock_2". Used in URLs and Home Assistant names,
// so it must be stable and safe in a path.
export function slugify(name) {
  return String(name).toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'camera'
}

// Credentials for the bridge's own HTTP server: created once and kept in the
// add-on's private /data, so Home Assistant's saved camera keeps working
// across restarts. Off the add-on they are new on every run.
export const AUTH_PATH = process.env.BRIDGE_AUTH_PATH || '/data/bridge_auth.json'

export function loadAuth(persist, chosenPassword = '') {
  // An owner-chosen password (option bridge_password) wins, so a camera can be
  // added by hand without the generated one ever being shown anywhere.
  if (chosenPassword) return { username: 'firemex', password: chosenPassword }
  if (persist) {
    try {
      const a = JSON.parse(fs.readFileSync(AUTH_PATH, 'utf8'))
      if (a.username && a.password && a.password.length >= 24) return a
    } catch { /* first start */ }
  }
  const a = { username: 'firemex', password: crypto.randomBytes(24).toString('base64url') }
  if (persist) fs.writeFileSync(AUTH_PATH, JSON.stringify(a), { mode: 0o600 })
  return a
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
  const inAddon = fs.existsSync(OPTIONS_PATH)
  let opts
  if (inAddon) {
    // Inside the FiremeX add-on: its options carry the EZVIZ settings under an
    // ezviz_ prefix (FiremeX's own `cameras` option means something else).
    const o = JSON.parse(fs.readFileSync(OPTIONS_PATH, 'utf8'))
    opts = {
      app_key: o.ezviz_app_key, app_secret: o.ezviz_app_secret, api: o.ezviz_api,
      cameras: o.ezviz_cameras || [], fps: o.ezviz_fps, hd: false,
      bridge_password: o.ezviz_bridge_password, register_in_home_assistant: true,
    }
  } else {
    const e = { ...readEnvFile(env.EZVIZ_ENV_FILE || path.join(os.homedir(), '.firemex-ezviz.env')), ...env }
    opts = {
      app_key: e.EZVIZ_APP_KEY, app_secret: e.EZVIZ_APP_SECRET, api: e.EZVIZ_API,
      cameras: (e.EZVIZ_SERIAL || fake)
        ? [{ name: e.EZVIZ_NAME || 'EZVIZ Camera', serial: e.EZVIZ_SERIAL || 'FAKE00001',
             verify_code: e.EZVIZ_VERIFY_CODE || 'ABCDEF', channel: Number(e.EZVIZ_CHANNEL || 1) }]
        : [],
      fps: Number(e.BRIDGE_FPS || 2), hd: e.BRIDGE_HD === '1',
      register_in_home_assistant: false,
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

  return {
    fake,
    appKey: opts.app_key, appSecret: opts.app_secret,
    api: String(opts.api || 'https://open.ezvizlife.com').replace(/\/$/, ''),
    cameras,
    fps: Math.min(Math.max(Number(opts.fps) || 2, 0.2), 5),
    hd: Boolean(opts.hd),
    port: Number(env.BRIDGE_PORT || 8095),
    inAddon,
    listenHost: inAddon ? '0.0.0.0' : '127.0.0.1',
    auth: loadAuth(inAddon, opts.bridge_password || ''),
    registerInHA: opts.register_in_home_assistant !== false && Boolean(env.SUPERVISOR_TOKEN),
    puppeteerPath: env.PUPPETEER_PATH || 'puppeteer-core',
    chromePath: env.CHROME_PATH || '',
    debug: env.BRIDGE_DEBUG === '1',
  }
}
