// Thin API client. In dev, Vite proxies /api -> backend (see vite.config.js).
// In prod, set VITE_API to the API origin (e.g. https://api.yourdomain.com).
const BASE = import.meta.env.VITE_API ?? '/api'
export const API_BASE = BASE

// WebSocket origin. When VITE_API is an absolute URL (prod), derive ws(s)://
// from it; otherwise (dev '/api' proxy) use the current page host.
export function wsBaseUrl() {
  const api = import.meta.env.VITE_API
  if (api && /^https?:\/\//i.test(api)) {
    const u = new URL(api)
    const proto = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${u.host}`
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}`
}

let authToken = null
export function setAuthToken(t) { authToken = t }
export function getAuthToken() { return authToken }

async function req(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  newMatch: (username, displayName) =>
    req('/match', { method: 'POST', body: JSON.stringify({ username, display_name: displayName || null }) }),
  pick: (matchId, playerName, slot) =>
    req(`/match/${matchId}/pick`, {
      method: 'POST',
      body: JSON.stringify({ player_name: playerName, slot }),
    }),
  record: (username) => req(`/record/${encodeURIComponent(username)}`),
  setAvatar: (username, avatar) =>
    req('/avatar', { method: 'POST', body: JSON.stringify({ username, avatar }) }),
  leaderboard: () => req('/leaderboard'),
  signup: (username, password, guest_id) =>
    req('/auth/signup', { method: 'POST', body: JSON.stringify({ username, password, guest_id }) }),
  login: (username, password) =>
    req('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => req('/auth/logout', { method: 'POST' }),
  me: () => req('/auth/me'),
}
