const API_BASE = '/api'

export async function apiFetch(path, options = {}) {
  const { headers, ...rest } = options
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(headers || {}) },
    ...rest,
  })
  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent('auth:unauthorized'))
  }
  return res
}

export async function apiJson(path, options) {
  const res = await apiFetch(path, options)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* non-JSON error body */ }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}
