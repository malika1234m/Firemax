// FiremeX EZVIZ bridge.
//
// EZVIZ cameras with Video Encryption ON only play in EZVIZ's own player, which
// decrypts with the camera's verification code. Home Assistant cannot read them
// at all. This bridge runs that official player in a headless browser, takes
// the decoded pictures, and serves each camera as an ordinary MJPEG camera that
// Home Assistant — and so FiremeX — can use:
//
//   EZVIZ camera ─(encrypted)─► EZVIZ cloud ─► this bridge (EZVIZ player + code)
//                                            ─► http://<bridge>:8095/<camera>/stream.mjpg
//                                               http://<bridge>:8095/<camera>/snapshot.jpg
//
// No encryption is broken: it is EZVIZ's own player, with the owner's own
// developer keys and verification codes.
//
// Settings come from /data/options.json when running as a Home Assistant
// add-on, otherwise from ~/.firemex-ezviz.env (one camera) for development.
// BRIDGE_FAKE=1 swaps the EZVIZ player for a simulated one (fake_player.html),
// so everything except the EZVIZ cloud can be tested without a camera.
import crypto from 'node:crypto'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { loadConfig } from './config.mjs'
import { getToken } from './ezviz.mjs'
import { registerCameras } from './homeassistant.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const CFG = loadConfig()
const log = (...a) => console.log(new Date().toISOString(), ...a)

// ── per-camera state: the newest decoded picture ───────────────────────────────
const cams = new Map(CFG.cameras.map((c) => [c.id, { ...c, latest: null, state: 'starting', error: null, frames: 0 }]))

// Every request needs the bridge's credentials. These URLs carry DECRYPTED
// camera video, so being reachable must not be enough to watch it: other
// add-ons share the internal network, and a development machine shares its
// LAN. Home Assistant is given the credentials when the camera is added.
const expected = Buffer.from('Basic ' + Buffer.from(`${CFG.auth.username}:${CFG.auth.password}`).toString('base64'))
function authorised(req) {
  const got = Buffer.from(req.headers.authorization || '')
  return got.length === expected.length && crypto.timingSafeEqual(got, expected)
}

const server = http.createServer((req, res) => {
  if (!authorised(req)) {
    res.writeHead(401, { 'WWW-Authenticate': 'Basic realm="FiremeX EZVIZ bridge"' })
    return res.end('authentication required')
  }
  const [, id, file] = (req.url.split('?')[0]).split('/')
  if (id === 'status') {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    return res.end(JSON.stringify([...cams.values()].map((c) => ({
      id: c.id, name: c.name, state: c.state, error: c.error, frames: c.frames,
      last_frame_age_s: c.latest ? (Date.now() - c.latest.at) / 1000 : null,
    }))))
  }
  const cam = cams.get(id)
  if (!cam) { res.writeHead(404); return res.end('unknown camera') }
  if (file === 'snapshot.jpg') {
    if (!cam.latest) { res.writeHead(503); return res.end('no frame yet') }
    res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Cache-Control': 'no-store' })
    return res.end(cam.latest.jpeg)
  }
  if (file === 'stream.mjpg') {
    res.writeHead(200, { 'Content-Type': 'multipart/x-mixed-replace; boundary=frame', 'Cache-Control': 'no-store' })
    let sent = 0
    const timer = setInterval(() => {
      if (!cam.latest || cam.latest.at === sent) return
      sent = cam.latest.at
      res.write(`--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${cam.latest.jpeg.length}\r\n\r\n`)
      res.write(cam.latest.jpeg); res.write('\r\n')
    }, 100)
    req.on('close', () => clearInterval(timer))
    return
  }
  res.writeHead(404); res.end()
})

// ── the headless EZVIZ player, one page per camera ─────────────────────────────
const puppeteer = (await import(CFG.puppeteerPath)).default
let browser = null
async function getBrowser() {
  if (browser?.connected) return browser
  browser = await puppeteer.launch({
    headless: true,
    executablePath: CFG.chromePath || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required', '--mute-audio'],
  })
  return browser
}

async function runCamera(cam) {
  const token = CFG.fake ? { accessToken: 'fake', domain: '', expiresAt: Date.now() + 7 * 864e5 }
                         : await getToken(CFG)
  const page = await (await getBrowser()).newPage()
  try {
    if (CFG.debug) page.on('console', (m) => log(`[${cam.id}]`, m.text()))
    await page.setViewport({ width: 1280, height: 720 })
    await page.evaluateOnNewDocument((cfg) => { window.BRIDGE = cfg },
      { accessToken: token.accessToken, domain: token.domain, serial: cam.serial,
        channel: cam.channel, verifyCode: cam.verifyCode, hd: CFG.hd })
    await page.goto('file://' + path.join(HERE, CFG.fake ? 'fake_player.html' : 'player.html'))

    const interval = 1000 / CFG.fps
    let misses = 0
    while (true) {
      const t0 = Date.now()
      const st = await page.evaluate(() => window.bridgeState)
      if (st?.status === 'error') throw new Error('player error: ' + JSON.stringify(st.error))
      const b64 = await page.evaluate(() => window.grabFrame())
      if (b64) {
        cam.latest = { jpeg: Buffer.from(b64.replace(/^data:image\/\w+;base64,/, ''), 'base64'), at: Date.now() }
        cam.frames++; misses = 0
        if (cam.state !== 'playing') { cam.state = 'playing'; cam.error = null; log(`${cam.name}: playing — frames flowing`) }
      } else if (++misses >= 30) {
        throw new Error('no picture for 30 attempts')
      }
      // Renew the EZVIZ token (valid 7 days) a day before it runs out.
      if (Date.now() > token.expiresAt - 864e5) throw new Error('token renewal')
      await new Promise((r) => setTimeout(r, Math.max(0, interval - (Date.now() - t0))))
    }
  } finally {
    await page.close().catch(() => {})
  }
}

// A fire camera must come back on its own after any failure — but with a
// growing pause, so a wrong setting does not hammer the EZVIZ cloud.
async function keepRunning(cam) {
  let backoff = 5
  while (true) {
    const started = Date.now()
    try { await runCamera(cam) } catch (e) {
      cam.state = 'reconnecting'; cam.error = e.message
      log(`${cam.name}: stopped (${e.message}); retry in ${backoff}s`)
    }
    if (Date.now() - started > 10 * 60e3) backoff = 5            // it had been working
    await new Promise((r) => setTimeout(r, backoff * 1000))
    backoff = Math.min(backoff * 2, 300)
  }
}

// In the add-on, Home Assistant reaches the bridge over the internal network,
// so it listens there (no port is published to the host). Anywhere else it
// listens on this machine only.
server.listen(CFG.port, CFG.listenHost, () => {
  log(`bridge on ${CFG.listenHost}:${CFG.port} — ${cams.size} camera(s)${CFG.fake ? ' (SIMULATED player)' : ''}`)
  if (!CFG.inAddon) log(`  credentials: ${CFG.auth.username} / ${CFG.auth.password}  (development only)`)
  for (const c of cams.values()) log(`  ${c.name}: /${c.id}/stream.mjpg  /${c.id}/snapshot.jpg`)
})
if (CFG.registerInHA) registerCameras(CFG, [...cams.values()]).catch((e) => log(`camera registration failed: ${e.message}`))
for (const cam of cams.values()) keepRunning(cam)
