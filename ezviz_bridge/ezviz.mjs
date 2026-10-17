// EZVIZ Open Platform access token.
//
// POST <api>/api/lapp/token/get with the developer AppKey/AppSecret returns a
// token valid for 7 days and `areaDomain`, the regional server the account
// lives on. The player must use that same server, or it cannot find the camera.
let cached = null

export async function getToken(cfg, fetchImpl = fetch) {
  if (cached && cached.key === cfg.appKey && cached.expiresAt - Date.now() > 864e5) return cached
  const res = await fetchImpl(`${cfg.api}/api/lapp/token/get`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ appKey: cfg.appKey, appSecret: cfg.appSecret }),
  })
  const body = await res.json()
  if (String(body.code) !== '200') {
    // Common ones: 10017 appKey does not exist, 10030 appKey and appSecret
    // do not match, 10005 appKey frozen. Said plainly in the add-on log.
    throw new Error(`EZVIZ token request refused: ${body.code} ${body.msg}`)
  }
  cached = {
    key: cfg.appKey,
    accessToken: body.data.accessToken,
    expiresAt: Number(body.data.expireTime),
    domain: body.data.areaDomain || cfg.api,
  }
  return cached
}

export function _resetTokenCache() { cached = null }
