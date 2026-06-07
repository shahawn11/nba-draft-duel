// Thin API client. In dev, Vite proxies /api -> backend (see vite.config.js).
const BASE = import.meta.env.VITE_API ?? '/api'

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
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
  newMatch: (username, mode = 'offline') =>
    req('/match', { method: 'POST', body: JSON.stringify({ username, mode }) }),
  pick: (matchId, playerName, slot) =>
    req(`/match/${matchId}/pick`, {
      method: 'POST',
      body: JSON.stringify({ player_name: playerName, slot }),
    }),
  record: (username) => req(`/record/${encodeURIComponent(username)}`),
}
