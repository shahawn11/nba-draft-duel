// Sequential draft with free slot choice + UX polish.
// Interaction: click a player card -> a modal shows the open slots that player
// can fill -> click a slot to draft them there. Ineligible players are locked.
import { useState } from 'react'

const SLOTS = ['PG', 'SG', 'SF', 'PF', 'C']

function LineupStrip({ filled, openSlots, lastSlot }) {
  const bySlot = Object.fromEntries(filled.map((f) => [f.slot, f]))
  return (
    <div className="lineup-strip">
      {SLOTS.map((slot) => {
        const f = bySlot[slot]
        const open = openSlots.includes(slot)
        const cls = ['slot-chip', f && 'done', open && 'open', slot === lastSlot && 'flash']
          .filter(Boolean)
          .join(' ')
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

function Candidate({ p, index, onSelect, busy }) {
  const eligible = p.eligible
  return (
    <button
      className={`candidate ${eligible ? 'selectable' : 'ineligible'}`}
      style={{ animationDelay: `${index * 30}ms` }}
      disabled={!eligible || busy}
      onClick={() => eligible && onSelect(p)}
    >
      <div className="cand-top">
        <span className="pos-badges">
          {p.eligible_positions.map((pos) => (
            <span key={pos} className="pos-badge">{pos}</span>
          ))}
        </span>
        {p.height_in ? <span className="cand-height">{Math.floor(p.height_in / 12)}'{p.height_in % 12}"</span> : null}
        {!eligible && (
          <span className="locked">{p.taken ? '✓ already drafted' : 'no open slot'}</span>
        )}
      </div>
      <div className="cand-name">{p.name}</div>
      <div className="cand-stats">
        <b>{p.ppg}</b> pts · <b>{p.rpg}</b> reb · <b>{p.apg}</b> ast
      </div>
      <div className="cand-stats sub">
        {p.spg} stl · {p.bpg} blk · impact {p.bpm}
      </div>
      {eligible && (
        <div className="cand-cta">
          Tap to draft → {p.eligible_slots.join(' / ')}
        </div>
      )}
    </button>
  )
}

function SlotModal({ player, onDraft, onCancel, busy }) {
  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="m-assign">Draft</div>
        <div className="m-player">{player.name}</div>
        <div className="m-stats">
          {player.ppg} pts · {player.rpg} reb · {player.apg} ast · impact {player.bpm}
        </div>
        <div className="m-assign">Choose a slot:</div>
        <div className="modal-slots">
          {player.eligible_slots.map((s) => (
            <button key={s} className="btn-confirm slot-choice" disabled={busy} onClick={() => onDraft(s)}>
              {busy ? '…' : s}
            </button>
          ))}
        </div>
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DraftBoard({ view, onPick, busy }) {
  const [selected, setSelected] = useState(null)
  const step = view.current_step
  const lastSlot = view.filled.length ? view.filled[view.filled.length - 1].slot : null
  const stepKey = `${step.decade}-${step.team}-${view.picks_made}`

  async function draft(slot) {
    await onPick(selected.name, slot)
    setSelected(null)
  }

  return (
    <div className="draft-board">
      <LineupStrip filled={view.filled} openSlots={view.open_slots} lastSlot={lastSlot} />

      <div className="step-head" key={stepKey + '-head'}>
        <div className="step-count">Pick {view.picks_made + 1} of {view.total_slots}</div>
        <div className="prompt-head">
          <span className="decade">{step.decade}</span>
          <span className="team">{step.team}</span>
        </div>
        <p className="hint">
          Top 10 of the decade · stats are {step.decade} averages · tap a player,
          then pick an open slot ({view.open_slots.join(' · ')})
        </p>
      </div>

      <div className="candidates" key={stepKey}>
        {step.candidates.map((p, i) => (
          <Candidate key={p.name} p={p} index={i} busy={busy} onSelect={setSelected} />
        ))}
      </div>

      {selected && (
        <SlotModal player={selected} busy={busy} onDraft={draft} onCancel={() => setSelected(null)} />
      )}
    </div>
  )
}
