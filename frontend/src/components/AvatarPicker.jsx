import { useState } from 'react'
import Avatar, { AVATARS } from './Avatar.jsx'

// Modal to choose your rank avatar. Locked avatars show why (reach the tier).
export default function AvatarPicker({ record, onSelect, onClose }) {
  const unlocked = new Set(record?.unlocked || ['amateur'])
  const current = record?.avatar || 'amateur'
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState('')

  async function choose(a) {
    if (!unlocked.has(a.id) || busy) return
    setBusy(a.id); setErr('')
    try {
      await onSelect(a.id)
      onClose()
    } catch (e) {
      setErr(e.message || 'Could not set avatar')
      setBusy(null)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="avatar-picker" onClick={(e) => e.stopPropagation()}>
        <div className="ap-head">
          <h3>Choose your avatar</h3>
          <button className="link-btn" onClick={onClose}>✕</button>
        </div>
        <p className="ap-sub">Unlock new avatars by climbing the rating ladder.</p>
        {err && <div className="error">{err}</div>}
        <div className="ap-grid">
          {AVATARS.map((a) => {
            const isUnlocked = unlocked.has(a.id)
            const isCurrent = current === a.id
            return (
              <button
                key={a.id}
                className={`ap-cell${isCurrent ? ' current' : ''}${isUnlocked ? '' : ' locked'}`}
                onClick={() => choose(a)}
                disabled={!isUnlocked || busy}
                title={isUnlocked ? a.tier : `Reach ${a.tier} (${a.min.toLocaleString()})`}
              >
                <Avatar id={a.id} size={64} locked={!isUnlocked} />
                <span className="ap-tier">{a.label}</span>
                <span className="ap-meta">
                  {isCurrent ? 'Equipped' : isUnlocked ? a.tier : `🔒 ${a.min.toLocaleString()}`}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
