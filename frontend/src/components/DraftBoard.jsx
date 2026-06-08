// Sequential draft with free slot choice + UX polish.
// Interaction: click a player card -> a modal shows the open slots that player
// can fill -> click a slot to draft them there. Ineligible players are locked.
import { useState, useEffect } from 'react'
import { startMusic, stopMusic } from '../music.js'
import TierBadge from './TierBadge.jsx'
import { tierClass } from '../tiers.js'

const SLOTS = ['PG', 'SG', 'SF', 'PF', 'C']

function Timer({ deadline }) {
  const [now, setNow] = useState(Date.now() / 1000)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 250)
    return () => clearInterval(id)
  }, [])
  const left = Math.max(0, Math.ceil(deadline - now))
  const pct = Math.max(0, Math.min(100, (left / 10) * 100))
  return (
    <div className="timer">
      <div className="timer-bar" style={{ width: `${pct}%` }} />
      <span className="timer-text">⏱ {left}s</span>
    </div>
  )
}

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

function BudgetMeter({ budget, spent, remaining }) {
  if (budget == null) return null
  const used = Math.max(0, Math.min(100, (spent / budget) * 100))
  const low = remaining <= 28          // can only afford a cheapest (D) player
  const tight = remaining <= 56 && !low
  return (
    <div className="budget-meter">
      <div className="budget-row">
        <span className="budget-cap">💰 Salary cap</span>
        <span className={`budget-left ${low ? 'low' : tight ? 'tight' : ''}`}>
          <b>{remaining}</b> left <span className="budget-of">/ {budget}</span>
        </span>
      </div>
      <div className="budget-track">
        <div className={`budget-fill ${low ? 'low' : tight ? 'tight' : ''}`} style={{ width: `${used}%` }} />
      </div>
    </div>
  )
}

function Candidate({ p, index, onSelect, busy, openSlots }) {
  const eligible = p.eligible
  const fitsOpenSlot = (p.eligible_positions || []).some((pos) => openSlots.includes(pos))
  // Why is this card locked? over-budget vs no open slot vs already drafted.
  const lockReason = p.taken
    ? '✓ already drafted'
    : (!p.affordable && fitsOpenSlot)
      ? `💰 over budget ($${p.cost})`
      : 'no open slot'
  return (
    <button
      className={`candidate tier-card ${tierClass(p.tier)} ${eligible ? 'selectable' : 'ineligible'} ${!eligible && !p.taken && !p.affordable && fitsOpenSlot ? 'overbudget' : ''}`}
      style={{ animationDelay: `${index * 30}ms` }}
      disabled={!eligible || busy}
      onClick={() => eligible && onSelect(p)}
    >
      <div className="cand-top">
        <TierBadge tier={p.tier} cost={p.cost} />
        <span className="pos-badges">
          {p.eligible_positions.map((pos) => (
            <span key={pos} className="pos-badge">{pos}</span>
          ))}
        </span>
        {p.height_in ? <span className="cand-height">{Math.floor(p.height_in / 12)}'{p.height_in % 12}"</span> : null}
        {!eligible && <span className="locked">{lockReason}</span>}
      </div>
      <div className="cand-name">{p.name}</div>
      {(() => {
        const hasPeak = !!p.peak_season
        const ppg = hasPeak ? p.decade_ppg : p.ppg
        const rpg = hasPeak ? p.decade_rpg : p.rpg
        const apg = hasPeak ? p.decade_apg : p.apg
        const spg = hasPeak ? p.decade_spg : p.spg
        const bpg = hasPeak ? p.decade_bpg : p.bpg
        return (
          <>
            <div className="cand-stats">
              <b>{ppg}</b> pts · <b>{rpg}</b> reb · <b>{apg}</b> ast
            </div>
            <div className="cand-stats sub">
              {spg} stl · {bpg} blk{hasPeak ? '' : ` · impact ${p.bpm}`}
            </div>
            {hasPeak && (
              <div className="cand-peak" title="Tier/cost use a 50/50 blend of this peak season and the decade average">
                ⭐ Peak {p.peak_season}: <b>{p.peak_ppg}</b>/{p.peak_rpg}/{p.peak_apg} · impact {p.peak_bpm}
              </div>
            )}
          </>
        )
      })()}
      {eligible && (
        <div className="cand-cta">
          Tap to draft (${p.cost}) → {p.eligible_slots.join(' / ')}
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
        <div className="m-player">
          <TierBadge tier={player.tier} cost={player.cost} /> {player.name}
        </div>
        <div className="m-stats">
          {player.peak_season ? player.decade_ppg : player.ppg} pts · {player.peak_season ? player.decade_rpg : player.rpg} reb · {player.peak_season ? player.decade_apg : player.apg} ast
          {!player.peak_season && <> · impact {player.bpm}</>}
        </div>
        {player.peak_season && (
          <div className="m-peak">⭐ Peak {player.peak_season}: <b>{player.peak_ppg}</b>/{player.peak_rpg}/{player.peak_apg} · impact {player.peak_bpm}</div>
        )}
        <div className="m-assign">Choose a slot (costs ${player.cost}):</div>
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

export default function DraftBoard({ view, onPick, busy, deadline, waiting, opponentPicks }) {
  const [selected, setSelected] = useState(null)
  useEffect(() => {
    startMusic()
    return () => stopMusic()
  }, [])
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

      <BudgetMeter budget={view.budget} spent={view.spent} remaining={view.remaining} />

      {deadline ? <Timer deadline={deadline} key={stepKey + '-t'} /> : null}

      <div className="step-head" key={stepKey + '-head'}>
        <div className="step-count">
          Pick {view.picks_made + 1} of {view.total_slots}
          {opponentPicks != null && (
            <span className="opp-progress"> · opponent: {opponentPicks}/{view.total_slots}</span>
          )}
        </div>
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
          <Candidate key={p.name} p={p} index={i} busy={busy || waiting}
                     onSelect={setSelected} openSlots={view.open_slots} />
        ))}
      </div>

      {waiting && <div className="waiting-banner">✅ Pick locked — waiting for your opponent…</div>}

      {selected && (
        <SlotModal player={selected} busy={busy} onDraft={draft} onCancel={() => setSelected(null)} />
      )}
    </div>
  )
}
