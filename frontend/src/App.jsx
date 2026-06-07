import { useState } from 'react'
import { api } from './api.js'
import DraftBoard from './components/DraftBoard.jsx'
import Results from './components/Results.jsx'

export default function App() {
  const [username, setUsername] = useState('')
  const [committedName, setCommittedName] = useState('')
  const [record, setRecord] = useState(null)
  const [view, setView] = useState(null) // latest step view from backend
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function startMatch(name) {
    setError('')
    setBusy(true)
    try {
      const v = await api.newMatch(name)
      setView(v)
      setResult(null)
      setCommittedName(name)
      setRecord(await api.record(name))
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
      if (res.done) {
        setResult(res.result)
        setRecord(res.result.record)
      } else {
        setView(res)
      }
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
        {committedName && record && (
          <div className="record">
            <span className="who">{committedName}</span>
            <span className="wlt">
              <b className="w">{record.wins}W</b> ·{' '}
              <b className="l">{record.losses}L</b> ·{' '}
              <b className="t">{record.ties}T</b>
            </span>
          </div>
        )}
      </header>

      {error && <div className="error">{error}</div>}

      {phase === 'setup' && (
        <div className="setup">
          <h2>Enter the arena</h2>
          <p className="hint">
            Offline mode: a random decade &amp; team is revealed for each of your
            five lineup slots — draft a player who fits, one pick at a time.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (username.trim()) startMatch(username.trim())
            }}
          >
            <input
              autoFocus
              placeholder="your name"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <button className="submit" disabled={busy || !username.trim()}>
              {busy ? 'Loading…' : 'Start match'}
            </button>
          </form>
        </div>
      )}

      {phase === 'drafting' && view && (
        <DraftBoard view={view} onPick={pick} busy={busy} />
      )}

      {phase === 'result' && result && (
        <Results result={result} onPlayAgain={() => startMatch(committedName)} />
      )}
    </div>
  )
}
