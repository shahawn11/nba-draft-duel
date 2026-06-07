// Sequential draft with free slot choice. Each step reveals a random
// decade x team and its top-10 (decade-averaged) players. Pick any player and
// assign them to any OPEN slot they're eligible for (slot buttons on each card).
// Players with no open eligible slot are shown but locked.

const SLOTS = ['PG', 'SG', 'SF', 'PF', 'C']

function LineupStrip({ filled, openSlots }) {
  const bySlot = Object.fromEntries(filled.map((f) => [f.slot, f]))
  return (
    <div className="lineup-strip">
      {SLOTS.map((slot) => {
        const f = bySlot[slot]
        const open = openSlots.includes(slot)
        const cls = ['slot-chip', f && 'done', open && 'open'].filter(Boolean).join(' ')
        return (
          <div className={cls} key={slot}>
            <span className="slot-label">{slot}</span>
            <span className="slot-name">{f ? f.name : open ? 'open' : '—'}</span>
          </div>
        )
      })}
    </div>
  )
}

function Candidate({ p, onPick, busy }) {
  return (
    <div className={`candidate ${!p.eligible ? 'ineligible' : ''}`}>
      <div className="cand-top">
        <span className="pos-badges">
          {p.eligible_positions.map((pos) => (
            <span key={pos} className="pos-badge">{pos}</span>
          ))}
        </span>
      </div>
      <div className="cand-name">{p.name}</div>
      <div className="cand-stats">
        <b>{p.ppg}</b> pts · <b>{p.rpg}</b> reb · <b>{p.apg}</b> ast
      </div>
      <div className="cand-stats sub">
        {p.spg} stl · {p.bpg} blk · impact {p.bpm}
      </div>
      {p.eligible ? (
        <div className="slot-pick">
          <span className="slot-pick-label">draft to:</span>
          {p.eligible_slots.map((s) => (
            <button key={s} className="slot-btn" disabled={busy} onClick={() => onPick(p.name, s)}>
              {s}
            </button>
          ))}
        </div>
      ) : (
        <div className="locked">no open slot</div>
      )}
    </div>
  )
}

export default function DraftBoard({ view, onPick, busy }) {
  const step = view.current_step
  return (
    <div className="draft-board">
      <LineupStrip filled={view.filled} openSlots={view.open_slots} />

      <div className="step-head">
        <div className="step-count">Pick {view.picks_made + 1} of {view.total_slots}</div>
        <div className="prompt-head">
          <span className="decade">{step.decade}</span>
          <span className="team">{step.team}</span>
        </div>
        <p className="hint">
          Top 10 of the decade · stats are {step.decade} averages · pick a player
          and assign them to an open slot they can play
          {' '}({view.open_slots.join(' · ')})
        </p>
      </div>

      <div className="candidates">
        {step.candidates.map((p) => (
          <Candidate key={p.name} p={p} busy={busy} onPick={onPick} />
        ))}
      </div>
    </div>
  )
}
