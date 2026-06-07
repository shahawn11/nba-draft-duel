import { useState, useEffect } from 'react'
import { api } from '../api.js'

const TIER_CLASS = {
  'Amateur': 'amateur', 'Pro': 'pro', 'All-Star': 'allstar',
  'Veteran': 'veteran', 'Hall-of-Fame': 'hof', 'GOAT': 'goat',
}

export default function Leaderboard({ onClose, highlight }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.leaderboard()
      .then((d) => setRows(d.leaderboard))
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="leaderboard">
      <div className="lb-head">
        <h2>🏆 Leaderboard</h2>
        {onClose && <button className="btn-cancel" onClick={onClose}>Close</button>}
      </div>
      {error && <div className="error">{error}</div>}
      {rows && rows.length === 0 && <p className="hint">No games played yet — be the first!</p>}
      {rows && rows.length > 0 && (
        <table className="lb-table">
          <thead>
            <tr><th>#</th><th>Player</th><th>Tier</th><th>Rating</th><th>W–L–T</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.username} className={highlight === r.username ? 'me' : ''}>
                <td className="rank">{i + 1}</td>
                <td className="lb-name">{r.username}</td>
                <td><span className={`tier-badge ${TIER_CLASS[r.tier] || ''}`}>{r.tier}</span></td>
                <td className="lb-rating">{r.rating}</td>
                <td className="lb-wlt">{r.wins}–{r.losses}–{r.ties}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!rows && !error && <p className="hint">Loading…</p>}
    </div>
  )
}
