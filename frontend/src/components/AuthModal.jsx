import { useState } from 'react'
import { api } from '../api.js'

export default function AuthModal({ guestId, onClose, onAuth }) {
  const [tab, setTab] = useState('login') // login | signup
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function clientCheck() {
    if (tab !== 'signup') return null
    if (password.length < 8) return 'Password must be at least 8 characters.'
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      return 'Password must include at least one letter and one number.'
    }
    if (password !== confirm) return 'Passwords do not match.'
    return null
  }

  async function submit(e) {
    e.preventDefault()
    const ce = clientCheck()
    if (ce) { setError(ce); return }
    setError('')
    setBusy(true)
    try {
      const data = tab === 'signup'
        ? await api.signup(username.trim(), password, guestId)
        : await api.login(username.trim(), password)
      onAuth(data) // { token, username, record }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onClose}>
      <div className="modal auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="auth-tabs">
          <button className={tab === 'login' ? 'active' : ''} onClick={() => setTab('login')} type="button">Log in</button>
          <button className={tab === 'signup' ? 'active' : ''} onClick={() => setTab('signup')} type="button">Sign up</button>
        </div>
        {tab === 'signup' && (
          <div className="hint auth-hint">
            <div>Your current guest record &amp; rating will carry over.</div>
            <div>Username: 3–20 letters/numbers/underscore.</div>
            <div>Password: 8+ chars with a letter and a number.</div>
          </div>
        )}
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit} className="auth-form">
          <input
            autoFocus
            placeholder="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            placeholder="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {tab === 'signup' && (
            <input
              type="password"
              placeholder="confirm password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          )}
          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="submit" className="btn-confirm" disabled={busy || !username.trim() || !password}>
              {busy ? '…' : tab === 'signup' ? 'Create account' : 'Log in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
