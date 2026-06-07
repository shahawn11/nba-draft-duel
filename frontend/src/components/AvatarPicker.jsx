import { useState } from 'react'
import Avatar, { AVATARS, ACHIEVEMENT_AVATARS } from './Avatar.jsx'

// Modal to choose your avatar. Locked avatars show how to unlock them.
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

  function Cell({ a, lockHint }) {
    const isUnlocked = unlocked.has(a.id)
    const isCurrent = current === a.id
    return (
      <button
        className={`ap-cell${isCurrent ? ' current' : ''}${isUnlocked ? '' : ' locked'}`}
        onClick={() => choose(a)}
        disabled={!isUnlocked || busy}
        title={isUnlocked ? a.label : lockHint}
      >
        <Avatar id={a.id} size={64} locked={!isUnlocked} />
        <span className="ap-tier">{a.label}</span>
        <span className="ap-meta">{isCurrent ? 'Equipped' : isUnlocked ? 'Unlocked' : `🔒 ${lockHint}`}</span>
      </button>
    )
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="avatar-picker" onClick={(e) => e.stopPropagation()}>
        <div className="ap-head">
          <h3>Choose your avatar</h3>
          <button className="link-btn" onClick={onClose}>✕</button>
        </div>
        {err && <div className="error">{err}</div>}

        <p className="ap-section">Ranks <span>— climb the rating ladder</span></p>
        <div className="ap-grid">
          {AVATARS.map((a) => (
            <Cell key={a.id} a={a} lockHint={`Reach ${a.tier} (${a.min.toLocaleString()})`} />
          ))}
        </div>

        <p className="ap-section">Achievements <span>— earned in-game</span></p>
        <div className="ap-grid">
          {ACHIEVEMENT_AVATARS.map((a) => (
            <Cell key={a.id} a={a} lockHint={a.how} />
          ))}
        </div>
      </div>
    </div>
  )
}
