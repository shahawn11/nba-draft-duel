// Sequential draft with free slot choice + UX polish:
//  - click a slot button -> confirmation modal (prevents misclicks)
//  - candidates fade/stagger in on each new step
//  - the slot you just filled flashes in the lineup strip
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

function Candidate({ p, index, onChoose, busy }) {
  return (
    <div
      className={`candidate ${!p.eligible ? 'ineligible' : ''}`}
      style={{ animationDelay: `${index * 30}ms` }}
    >
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
            <button key={s} className="slot-btn" disabled={busy} onClick={() => onChoose(p, s)}>
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

function ConfirmModal({ pending, onConfirm, onCancel, busy }) {
  const p = pending.player
  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="m-assign">Draft</div>
        <div className="m-player">{p.name}</div>
        <div className="m-assign">
          to your <span className="m-slot">{pending.slot}</span>
        </div>
        <div className="m-stats">
          {p.ppg} pts · {p.rpg} reb · {p.apg} ast · impact {p.bpm}
        </div>
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button className="btn-confirm" onClick={onConfirm} disabled={busy}>
            {busy ? 'Drafting…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DraftBoard({ view, onPick, busy }) {
  const [pending, setPending] = useState(null)
  const step = view.current_step
  const lastSlot = view.filled.length ? view.filled[view.filled.length - 1].slot : null
  // remount the candidate grid each step so the entrance animation replays
  const stepKey = `${step.decade}-${step.team}-${view.picks_made}`

  async function confirm() {
    const { player, slot } = pending
    await onPick(player.name, slot)
    setPending(null)
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
          Top 10 of the decade · stats are {step.decade} averages · pick a player
          and assign them to an open slot ({view.open_slots.join(' · ')})
        </p>
      </div>

      <div className="candidates" key={stepKey}>
        {step.candidates.map((p, i) => (
          <Candidate key={p.name} p={p} index={i} busy={busy} onChoose={(player, slot) => setPending({ player, slot })} />
        ))}
      </div>

      {pending && (
        <ConfirmModal
          pending={pending}
          busy={busy}
          onConfirm={confirm}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  )
}
