// Results screen: outcome banner, final scores, head-to-head matchups,
// both scored lineups, and positional-fit notes.
import { useState, useEffect } from 'react'

function useCountUp(from, to, ms = 1100) {
  const [v, setV] = useState(from)
  useEffect(() => {
    if (from === to) { setV(to); return }
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setV(to); return
    }
    const start = performance.now()
    let raf
    const tick = (now) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      setV(Math.round(from + (to - from) * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [from, to, ms])
  return v
}

const CONFETTI_COLORS = ['#ff7a00', '#2ecc71', '#3a86ff', '#ffd700', '#e74c3c', '#a35bff']

function Confetti() {
  return (
    <div className="confetti" aria-hidden="true">
      {Array.from({ length: 28 }).map((_, i) => (
        <span
          key={i}
          style={{
            left: `${(i / 28) * 100}%`,
            background: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
            animationDelay: `${(i % 7) * 0.12}s`,
            animationDuration: `${1.8 + (i % 5) * 0.25}s`,
          }}
        />
      ))}
    </div>
  )
}

function PromotionOverlay({ tier, onDismiss }) {
  const cls = (tier || '').toLowerCase().replace(/[^a-z]/g, '')
  return (
    <div className="promo-overlay" onClick={onDismiss}>
      <Confetti />
      <div className="promo-card">
        <div className="promo-sub">TIER UP!</div>
        <div className={`promo-tier tier-badge ${cls}`}>{tier}</div>
        <div className="promo-msg">You've been promoted to <b>{tier}</b> 🎉</div>
        <button className="submit" onClick={onDismiss}>Nice!</button>
      </div>
    </div>
  )
}

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
              {p.height_in ? <span className="sp-ht">{Math.floor(p.height_in / 12)}'{p.height_in % 12}"</span> : null}
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
  const ranked = result.ranked
  const newRating = result.record ? result.record.rating : 0
  const oldRating = newRating - (result.rating_change || 0)
  const shownRating = useCountUp(oldRating, newRating)
  const [showPromo, setShowPromo] = useState(!!result.promoted)
  useEffect(() => { setShowPromo(!!result.promoted) }, [result])
  const bannerClass = tied ? 'tie' : won ? 'win' : 'loss'
  const bannerText = tied ? 'TIE GAME' : won ? 'YOU WIN' : 'YOU LOSE'

  // Reveal sequence: show the positional matchups first, then a 3s countdown,
  // then the full win/lose screen.
  const reduceMotion = typeof window !== 'undefined' && window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const [phase, setPhase] = useState(reduceMotion ? 'full' : 'reveal')
  const [count, setCount] = useState(3)
  useEffect(() => {
    if (phase !== 'reveal') return
    if (count <= 0) { setPhase('full'); return }
    const id = setTimeout(() => setCount((c) => c - 1), 1000)
    return () => clearTimeout(id)
  }, [phase, count])

  const matchups = (showTally) => (
    <div className="matchups">
      <h3>Positional matchups{showTally ? ` (${result.your_matchup_wins}–${result.opponent_matchup_wins})` : ''}</h3>
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
  )

  if (phase === 'reveal') {
    return (
      <div className="results">
        <h2 className="reveal-title">Positional Matchups</h2>
        {matchups(false)}
        <div className="reveal-countdown">
          Final score in <b key={count} className="count-num">{count}</b>…
        </div>
      </div>
    )
  }

  return (
    <div className="results">
      <div className={`banner ${bannerClass}`}>
        <span className="banner-text">{bannerText}</span>
        <span className="final-score">
          {result.your_final.toFixed(1)} – {result.opponent_final.toFixed(1)}
        </span>
        <span className="vs-team">vs {result.opponent_team}</span>
        {result.ranked ? (
          <span className="rating-change">
            <b className={result.rating_change >= 0 ? 'up' : 'down'}>
              {result.rating_change >= 0 ? '+' : ''}{result.rating_change} rating
            </b>
            {result.record && <> → <b className="rating-now">{shownRating}</b> ({result.record.tier})</>}
          </span>
        ) : (
          <span className="rating-change unranked">Offline · unranked (no rating change)</span>
        )}
      </div>

      {showPromo && (
        <PromotionOverlay tier={result.record.tier} onDismiss={() => setShowPromo(false)} />
      )}

      {matchups(true)}

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
