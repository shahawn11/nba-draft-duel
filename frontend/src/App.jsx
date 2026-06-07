import { useState, useEffect } from 'react'
import { api, setAuthToken } from './api.js'
import DraftBoard from './components/DraftBoard.jsx'
import Results from './components/Results.jsx'
import LivePvP from './components/LivePvP.jsx'
import Leaderboard from './components/Leaderboard.jsx'
import AuthModal from './components/AuthModal.jsx'
import { isMuted, toggleMuted } from './audio.js'

function loadAuth() {
  try { return JSON.parse(localStorage.getItem('ndd_auth') || 'null') } catch { return null }
}
function getGuestId() {
  let g = localStorage.getItem('ndd_guest')
  if (!g) { g = 'guest_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ndd_guest', g) }
  return g
}

export default function App() {
  const [guestId] = useState(getGuestId)
  const [auth, setAuth] = useState(loadAuth)
  const [guestName, setGuestName] = useState(() => localStorage.getItem('ndd_guest_name') || '')
  const [mode, setMode] = useState('offline')
  const [committedMode, setCommittedMode] = useState('offline')
  const [record, setRecord] = useState(null)
  const [view, setView] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [live, setLive] = useState(false)
  const [showLeaderboard, setShowLeaderboard] = useState(false)
  const [showAuth, setShowAuth] = useState(false)
  const [muted, setMuted] = useState(isMuted())

  const identity = (auth && auth.username) || guestId
  const loggedIn = !!(auth && auth.username)
  const displayName = loggedIn ? null : (guestName.trim() || null)

  function setGuest(name) {
    setGuestName(name)
    try { localStorage.setItem('ndd_guest_name', name) } catch { /* */ }
  }

  // On load: restore token, fetch record, validate session.
  useEffect(() => {
    if (auth && auth.token) setAuthToken(auth.token)
    api.record(identity).then(setRecord).catch(() => {})
    if (auth && auth.token) {
      api.me().then((d) => setRecord(d.record)).catch(() => {
        setAuth(null); localStorage.removeItem('ndd_auth'); setAuthToken(null)
        api.record(guestId).then(setRecord).catch(() => {})
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function onAuth(data) {
    const a = { token: data.token, username: data.username }
    setAuth(a)
    localStorage.setItem('ndd_auth', JSON.stringify(a))
    setAuthToken(data.token)
    setRecord(data.record)
    setShowAuth(false)
  }

  function logout() {
    api.logout().catch(() => {})
    setAuth(null)
    localStorage.removeItem('ndd_auth')
    setAuthToken(null)
    api.record(guestId).then(setRecord).catch(() => {})
  }

  async function startMatch(chosenMode = 'offline') {
    setCommittedMode(chosenMode)
    if (chosenMode === 'pvp') {
      setLive(true)
      try { setRecord(await api.record(identity)) } catch { /* */ }
      return
    }
    setLive(false)
    setError('')
    setBusy(true)
    try {
      const v = await api.newMatch(identity, displayName)
      setView(v)
      setResult(null)
      setRecord(await api.record(identity))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function pick(playerName, slot) {
    setError('')
    setBusy(true)
    try {
      const res = await api.pick(view.match_id, playerName, slot)
      if (res.done) { setResult(res.result); setRecord(res.result.record) }
      else setView(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const phase = result ? 'result' : view ? 'drafting' : 'setup'

  return (
    <div className="app">
      <header>
        <h1>🏀 NBA Draft Duel</h1>
        <div className="header-right">
          <button className="lb-toggle" onClick={() => { toggleMuted(); setMuted(isMuted()) }} title={muted ? 'Unmute' : 'Mute'}>
            {muted ? '🔇' : '🔊'}
          </button>
          <button className="lb-toggle" onClick={() => setShowLeaderboard((s) => !s)} title="Leaderboard">
            🏆 {showLeaderboard ? 'Back' : 'Leaderboard'}
          </button>
          {loggedIn
            ? <button className="lb-toggle" onClick={logout}>Log out</button>
            : <button className="lb-toggle" onClick={() => setShowAuth(true)}>Log in / Sign up</button>}
          {record && (
            <div className="record">
              <span className="who">{loggedIn ? identity : (guestName.trim() || 'Guest')}</span>
              <span className="rating-line">
                {record.tier && (
                  <span className={`tier-badge ${(record.tier || '').toLowerCase().replace(/[^a-z]/g, '')}`}>
                    {record.tier}
                  </span>
                )}
                {record.rating != null && <b className="rating-num">{record.rating}</b>}
              </span>
              <span className="wlt">
                <b className="w">{record.wins}W</b> · <b className="l">{record.losses}L</b> · <b className="t">{record.ties}T</b>
              </span>
            </div>
          )}
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      {showAuth && <AuthModal guestId={guestId} onClose={() => setShowAuth(false)} onAuth={onAuth} />}

      {showLeaderboard && <Leaderboard onClose={() => setShowLeaderboard(false)} highlight={identity} />}

      {!showLeaderboard && live && (
        <LivePvP username={identity} token={auth && auth.token} displayName={displayName} onExit={() => setLive(false)} onRecord={setRecord} meRecord={record} />
      )}

      {!showLeaderboard && !live && phase === 'setup' && (
        <div className="setup">
          <h2>Enter the arena</h2>
          <p className="hint">
            Playing as <b>{loggedIn ? identity : (guestName.trim() || 'Guest')}</b>
            {!loggedIn && <> — <button className="link-btn" onClick={() => setShowAuth(true)}>sign up</button> to keep your record.</>}
          </p>
          {!loggedIn && (
            <input
              className="guest-name"
              placeholder="guest name (optional)"
              maxLength={24}
              value={guestName}
              onChange={(e) => setGuest(e.target.value)}
            />
          )}
          <div className="mode-toggle">
            <button className={`mode-btn ${mode === 'offline' ? 'active' : ''}`} onClick={() => setMode('offline')} type="button">
              🏀 Offline
              <span className="mode-sub">unranked · vs a current NBA starting five</span>
            </button>
            <button className={`mode-btn ${mode === 'pvp' ? 'active' : ''}`} onClick={() => setMode('pvp')} type="button">
              ⚔️ PvP
              <span className="mode-sub">ranked · real-time head-to-head draft</span>
            </button>
          </div>
          <button className="submit" disabled={busy} onClick={() => startMatch(mode)}>
            {busy ? 'Loading…' : 'Start match'}
          </button>
        </div>
      )}

      {!showLeaderboard && phase === 'drafting' && view && (
        <DraftBoard view={view} onPick={pick} busy={busy} />
      )}

      {!showLeaderboard && phase === 'result' && result && (
        <Results result={result} onPlayAgain={() => startMatch(committedMode)} />
      )}
    </div>
  )
}
