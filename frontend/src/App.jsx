import { useState, useEffect } from 'react'
import { api, setAuthToken } from './api.js'
import DraftBoard from './components/DraftBoard.jsx'
import Results from './components/Results.jsx'
import LivePvP from './components/LivePvP.jsx'
import Leaderboard from './components/Leaderboard.jsx'
import AuthModal from './components/AuthModal.jsx'
import Avatar from './components/Avatar.jsx'
import AvatarPicker from './components/AvatarPicker.jsx'
import ConfirmModal from './components/ConfirmModal.jsx'
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
  const [showAvatar, setShowAvatar] = useState(false)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const [liveActive, setLiveActive] = useState(false)
  const [muted, setMuted] = useState(isMuted())

  const identity = (auth && auth.username) || guestId
  const loggedIn = !!(auth && auth.username)
  const displayName = loggedIn ? null : (guestName.trim() || null)
  // A guest name is locked once committed server-side (display_name set to a
  // custom value). Only signing up can change it after that.
  const guestNamed = !loggedIn && !!record && !!record.display_name && record.display_name !== guestId

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

  async function chooseAvatar(avatarId) {
    const rec = await api.setAvatar(identity, avatarId)
    setRecord(rec)
  }

  function doGoHome() {
    setResult(null)
    setView(null)
    setLive(false)
    setShowLeaderboard(false)
    setError('')
    setConfirmLeave(false)
    setLiveActive(false)
  }

  function goHome() {
    if (live && liveActive) { setConfirmLeave(true); return }
    doGoHome()
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
        <h1 className="brand" onClick={goHome} title="Home" role="button" tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') goHome() }}>
          <span className="brand-ball">🏀</span>
          <span className="brand-5v5">5<span className="brand-v">v</span>5</span>
          <span className="brand-duel">DUEL</span>
        </h1>
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
            <button className="identity-card" onClick={() => setShowAvatar(true)} title="Change avatar">
              <Avatar id={record.avatar || 'amateur'} size={44} />
              <span className="id-text">
                <span className="id-name">{loggedIn ? identity : (guestName.trim() || 'Guest')}</span>
                <span className="id-stats">
                  {record.tier && (
                    <span className={`tier-badge ${(record.tier || '').toLowerCase().replace(/[^a-z]/g, '')}`}>
                      {record.tier}
                    </span>
                  )}
                  {record.rating != null && <b className="rating-num">{record.rating}</b>}
                  <span className="wl"><b className="w">{record.wins}W</b>·<b className="l">{record.losses}L</b></span>
                </span>
              </span>
            </button>
          )}
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      {showAuth && <AuthModal guestId={guestId} onClose={() => setShowAuth(false)} onAuth={onAuth} />}

      {showAvatar && record && (
        <AvatarPicker record={record} onSelect={chooseAvatar} onClose={() => setShowAvatar(false)} />
      )}

      <ConfirmModal
        open={confirmLeave}
        title="Leave the live match?"
        message="If a game is in progress, this counts as a forfeit (your opponent wins)."
        confirmLabel="Leave match"
        cancelLabel="Stay"
        danger
        onConfirm={doGoHome}
        onCancel={() => setConfirmLeave(false)}
      />

      {showLeaderboard && <Leaderboard onClose={() => setShowLeaderboard(false)} highlight={identity} />}

      {!showLeaderboard && live && (
        <LivePvP username={identity} token={auth && auth.token} displayName={displayName} onExit={() => setLive(false)} onRecord={setRecord} meRecord={record} onActive={setLiveActive} />
      )}

      {!showLeaderboard && !live && phase === 'setup' && (
        <div className="setup">
          <h2>Enter the arena</h2>
          <p className="hint">
            Playing as <b>{loggedIn ? identity : (guestName.trim() || 'Guest')}</b>
            {!loggedIn && <> — <button className="link-btn" onClick={() => setShowAuth(true)}>sign up</button> to keep your record.</>}
          </p>
          {!loggedIn && (guestNamed ? (
            <p className="hint guest-locked">🔒 Guest name set — <button className="link-btn" onClick={() => setShowAuth(true)}>sign up</button> to change it.</p>
          ) : (
            <input
              className="guest-name"
              placeholder="guest name (optional)"
              maxLength={24}
              value={guestName}
              onChange={(e) => setGuest(e.target.value)}
            />
          ))}
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
