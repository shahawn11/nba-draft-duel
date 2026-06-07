// Results screen: outcome banner, final scores, head-to-head matchups,
// both scored lineups, and positional-fit notes.

function Lineup({ title, team, highlight }) {
  return (
    <div className={`lineup ${highlight ? 'highlight' : ''}`}>
      <h3>{title}</h3>
      <ul className="scored-players">
        {team.players.map((p) => (
          <li key={p.name}>
            <div className="sp-head">
              <span className="pos-badge">{p.position}</span>
              <span className="sp-name">{p.name}</span>
              <span className="sp-rating" title="player rating">{p.rating}</span>
            </div>
            <div className="sp-stats">
              <b>{p.game?.pts ?? 0}</b> pts · <b>{p.game?.reb ?? 0}</b> reb · <b>{p.game?.ast ?? 0}</b> ast
              {' · '}{p.game?.stl ?? 0} stl · {p.game?.blk ?? 0} blk
              {p.team || p.decade ? (
                <span className="sp-prov"> — {p.decade} {p.team}</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {team.fit_notes.length > 0 && (
        <ul className="fit-notes">
          {team.fit_notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function Results({ result, onPlayAgain }) {
  const won = result.outcome === 'win'
  const tied = result.outcome === 'tie'
  const bannerClass = tied ? 'tie' : won ? 'win' : 'loss'
  const bannerText = tied ? 'TIE GAME' : won ? 'YOU WIN' : 'YOU LOSE'

  return (
    <div className="results">
      <div className={`banner ${bannerClass}`}>
        <span className="banner-text">{bannerText}</span>
        <span className="final-score">
          {result.your_final.toFixed(1)} – {result.opponent_final.toFixed(1)}
        </span>
        <span className="vs-team">vs {result.opponent_team}</span>
      </div>

      <div className="matchups">
        <h3>Positional matchups ({result.your_matchup_wins}–{result.opponent_matchup_wins})</h3>
        {result.matchups.map((m, i) => (
          <div className={`matchup ${m.winner === 'home' ? 'you' : m.winner === 'away' ? 'opp' : 'even'}`} key={m.position} style={{ animationDelay: `${i * 70}ms` }}>
            <div className="matchup-row">
              <span className="m-pos">{m.position}</span>
              <span className="m-home">{m.home_player} · {m.home_score.toFixed(1)}</span>
              <span className="m-vs">vs</span>
              <span className="m-away">{m.away_score.toFixed(1)} · {m.away_player}</span>
            </div>
            {m.note && <div className="matchup-note">⚠ {m.note}</div>}
          </div>
        ))}
      </div>

      <div className="lineups">
        <Lineup title="Your 5" team={result.your_team} highlight={won} />
        <Lineup title={result.opponent_team} team={result.opponent_team_scored} highlight={!won && !tied} />
      </div>

      <button className="submit" onClick={onPlayAgain}>
        Play again ↻
      </button>
    </div>
  )
}
