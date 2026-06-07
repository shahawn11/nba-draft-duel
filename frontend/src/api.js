// Thin API client. In dev, Vite proxies /api -> backend (see vite.config.js).
const BASE = import.meta.env.VITE_API ?? '/api'

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
  leaderboard: () => req('/leaderboard'),
  signup: (username, password, guest_id) =>
    req('/auth/signup', { method: 'POST', body: JSON.stringify({ username, password, guest_id }) }),
  login: (username, password) =>
    req('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => req('/auth/logout', { method: 'POST' }),
  me: () => req('/auth/me'),
}
