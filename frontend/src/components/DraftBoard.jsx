// Sequential draft: shows the lineup-so-far, the current slot to fill, the
// randomly revealed decade x team, and that franchise's top-10 (decade-averaged)
// players. Only players eligible for the current slot are selectable.

const SLOTS = ['PG', 'SG', 'SF', 'PF', 'C']

function LineupStrip({ filled, currentSlot }) {
  const bySlot = Object.fromEntries(filled.map((f) => [f.slot, f]))
  return (
    <div className="lineup-strip">
      {SLOTS.map((slot) => {
        const f = bySlot[slot]
        const isCurrent = slot === currentSlot
        const cls = ['slot-chip', f && 'done', isCurrent && 'current']
          .filter(Boolean)
          .join(' ')
        return (
          <div className={cls} key={slot}>
            <span className="slot-label">{slot}</span>
            <span className="slot-name">{f ? f.name : isCurrent ? 'drafting…' : '—'}</span>
          </div>
        )
      })}
    </div>
  )
}

function PosBadges({ positions, slot }) {
  return (
    <span className="pos-badges">
      {positions.map((p) => (
        <span key={p} className={`pos-badge ${p === slot ? 'match' : ''}`}>{p}</span>
      ))}
    </span>
  )
}

function Candidate({ p, slot, disabled, onPick, busy }) {
  const cls = ['candidate', !p.eligible && 'ineligible'].filter(Boolean).join(' ')
  return (
    <button className={cls} disabled={disabled || busy} onClick={onPick}>
      <div className="cand-top">
        <PosBadges positions={p.eligible_positions} slot={slot} />
        {!p.eligible && <span className="locked">can't play {slot}</span>}
      </div>
      <div className="cand-name">{p.name}</div>
      <div className="cand-stats">
        <b>{p.ppg}</b> pts · <b>{p.rpg}</b> reb · <b>{p.apg}</b> ast
      </div>
      <div className="cand-stats sub">
        {p.spg} stl · {p.bpg} blk · impact {p.bpm}
      </div>
    </button>
  )
}

export default function DraftBoard({ view, onPick, busy }) {
  const step = view.current_step
  const slot = step.slot

  return (
    <div className="draft-board">
      <LineupStrip filled={view.filled} currentSlot={slot} />

      <div className="step-head">
        <div className="step-count">
          Pick {view.picks_made + 1} of {view.total_slots}
        </div>
        <h2>
          Draft your <span className="slot-hi">{slot}</span>
        </h2>
        <div className="prompt-head">
          <span className="decade">{step.decade}</span>
          <span className="team">{step.team}</span>
        </div>
        <p className="hint">
          Top 10 of the decade · stats are {step.decade} averages · only{' '}
          <span className="slot-hi">{slot}</span>-eligible players can be picked
        </p>
      </div>

      <div className="candidates">
        {step.candidates.map((p) => (
          <Candidate
            key={p.name}
            p={p}
            slot={slot}
            disabled={!p.eligible}
            busy={busy}
            onPick={() => onPick(p.name)}
          />
        ))}
      </div>
    </div>
  )
}
