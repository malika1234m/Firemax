/**
 * Everything the website needs to know about the Home Assistant add-on.
 *
 * The website never talks to the customer's Home Assistant. It hands out the
 * access token, and learns that an add-on is connected only when that add-on
 * checks its token with us (licence activations). Detection, cameras and
 * alerts stay in Home Assistant.
 */

export const REPO_URL = 'https://github.com/malika1234m/Firemax'
export const ADDON_NAME = 'FiremeX Fire & Smoke Detection (Local)'
export const DOCS_URL = `${REPO_URL}/blob/main/addon/firemex-local/DOCS.md`
export const CHANGELOG_URL = `${REPO_URL}/blob/main/addon/firemex-local/CHANGELOG.md`

// The Supervisor names an add-on from a store repository
// "<first 8 hex of sha1(lower-cased repository URL)>_<slug>".
const ADDON_SLUG = 'bd0c1f44_firemex_local'
const REPO_PARAM = encodeURIComponent(REPO_URL)

// my.home-assistant.io forwards to the customer's own Home Assistant (it asks
// for its address once, then remembers it). This link opens the FiremeX
// add-on's page; when the FiremeX repository is not added yet, Home Assistant
// first offers to add it, with the address already typed in.
export const OPEN_ADDON_URL =
  `https://my.home-assistant.io/redirect/supervisor_addon/?addon=${ADDON_SLUG}&repository_url=${REPO_PARAM}`

// Opens the add-on store's "Add repository" dialog with our address filled in.
export const ADD_REPO_URL =
  `https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=${REPO_PARAM}`

// The add-on re-checks its token once a day while it runs, so anything older
// than a day and a bit means it has stopped, lost internet, or lost its token.
const QUIET_AFTER_MS = 26 * 3600 * 1000

/** Summarise the installations using the org's token into one status. */
export function connectionStatus(installs) {
  if (!installs) return { state: 'loading' }
  if (installs.length === 0) return { state: 'never', label: 'Not connected yet' }
  const latest = installs.reduce((a, b) => (new Date(a.last_seen) > new Date(b.last_seen) ? a : b))
  const lastSeen = new Date(latest.last_seen)
  const quiet = Date.now() - lastSeen.getTime() > QUIET_AFTER_MS
  return {
    state: quiet ? 'quiet' : 'connected',
    label: quiet ? 'Not heard from recently' : 'Connected',
    lastSeen,
    version: latest.addon_version,
    count: installs.length,
  }
}

export const STATUS_STYLE = {
  connected: 'bg-safe/10 text-safe border-safe/25',
  quiet:     'bg-warn/10 text-warn border-warn/25',
  never:     'bg-white/[0.04] text-slate-400 border-white/[0.1]',
  loading:   'bg-white/[0.04] text-slate-500 border-white/[0.08]',
}

/** "3 minutes ago", "2 days ago" — for last-communication times. */
export function timeAgo(date) {
  const s = Math.max(0, Math.round((Date.now() - new Date(date).getTime()) / 1000))
  if (s < 60) return 'just now'
  const units = [['day', 86400], ['hour', 3600], ['minute', 60]]
  for (const [name, size] of units) {
    if (s >= size) {
      const n = Math.floor(s / size)
      return `${n} ${name}${n === 1 ? '' : 's'} ago`
    }
  }
  return 'just now'
}

/** What is new in the add-on, newest first — shown on the website so
 *  customers know to update. Keep in step with addon/firemex-local/CHANGELOG.md. */
export const WHATS_NEW = [
  {
    version: '1.7.0',
    items: [
      'Your licence now carries how many cameras your plan covers, and is renewed every day.',
      'The website shows how many cameras the add-on is watching.',
      'A copy of the add-on on a second machine can no longer share your licence.',
    ],
  },
  {
    version: '1.6.0',
    items: [
      'New fire model (model-v5) that recognises small flames — a lighter or candle is seen as a small flame and never raises an alarm.',
      'Burning-paper fires are still caught in nearly 9 of 10 checked frames.',
    ],
  },
  {
    version: '1.5.0',
    items: [
      'YOLO26 fire model (model-v4): better on every test set than the model before it.',
      'Built for many cameras: a compact camera wall, with alerting cameras on top.',
      'History with an evidence photo for every detection.',
      'One shared checking budget, so 20 cameras on a Raspberry Pi all stay current.',
    ],
  },
  {
    version: '1.4.0',
    items: [
      'Simpler dashboard: Home, Emergency and History tabs.',
      'Alerts on your phone through the Home Assistant app.',
      'Encrypted EZVIZ cameras supported.',
    ],
  },
]
