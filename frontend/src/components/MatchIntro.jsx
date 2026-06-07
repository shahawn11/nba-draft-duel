// Shown right after matchmaking, before drafting: both players' name/rating/
// record slide in from opposite sides and collide in the middle.
import { useEffect } from 'react'
import { playClash } from '../sound.js'
import Avatar from './Avatar.jsx'
import { nameLabel } from '../nameLabel.js'

function tierCls(tier) {
  return (tier || '').toLowerCase().replace(/[^a-z]/g, '')
}

function Fighter({ side, name, record }) {
  const label = record ? nameLabel(record) : (name || 'Player')
  return (
    <div className={`fighter ${side}`}>
      <Avatar id={(record && record.avatar) || 'amateur'} size={56} />
      <div className="fighter-name">{label}{record && record.on_streak && <span title={`${record.win_streak}-game win streak`}> 🔥</span>}</div>
      {record && (
        <>
          <span className={`tier-badge ${tierCls(record.tier)}`}>{record.tier}</span>
          <div className="fighter-rating">{record.rating}</div>
          <div className="fighter-wlt">{record.wins}W · {record.losses}L</div>
        </>
      )}
    </div>
  )
}

export default function MatchIntro({ me, meRecord, opponent, opponentRecord }) {
  useEffect(() => {
    const id = setTimeout(() => playClash(), 560) // synced to the VS clash pop
    return () => clearTimeout(id)
  }, [])
  return (
    <div className="match-intro">
      <Fighter side="left" name={me} record={meRecord} />
      <div className="vs-clash">VS</div>
      <Fighter side="right" name={opponent} record={opponentRecord} />
    </div>
  )
}
