import { useState } from 'react'
import { api } from './api.js'
import DraftBoard from './components/DraftBoard.jsx'
import Results from './components/Results.jsx'

export default function App() {
  const [username, setUsername] = useState('')
  const [committedName, setCommittedName] = useState('')
  const [record, setRecord] = useState(null)
  const [match, setMatch] = useState(null)
  const [picks, setPicks] = useState({}) // promptIndex -> playerName
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function startMatch(name) {
    setError('')
    setBusy(true)
    try {
      const m = await api.newMatch(name)
      setMatch(m)
      setPicks({})
      setResult(null)
      setCommittedName(name)
      setRecord(await api.record(name))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function pick(promptIndex, playerName) {
    setPicks((prev) => ({ ...prev, [promptIndex]: playerName }))
  }

  async function submitDraft() {
    setError('')
    setBusy(true)
    try {
      const picksArr = Object.entries(picks).map(([idx, name]) => ({
        prompt_index: Number(idx),
        player_name: name,
      }))
      const res = await api.submitDraft(match.match_id, picksArr)
      setResult(res)
      setRecord(res.record)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const phase = result ? 'result' : match ? 'drafting' : 'setup'

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
          <p className="hint">Offline mode: draft a starting 5 against a random current NBA lineup.</p>
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

      {phase === 'drafting' && match && (
        <DraftBoard
          prompts={match.prompts}
          picks={picks}
          onPick={pick}
          onSubmit={submitDraft}
          submitting={busy}
        />
      )}

      {phase === 'result' && result && (
        <Results result={result} onPlayAgain={() => startMatch(committedName)} />
      )}
    </div>
  )
}
