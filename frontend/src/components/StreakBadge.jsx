// Win-streak badge: a small raised 🔥 + the streak count in a fiery gradient.
// Renders nothing unless the record is on a streak (>= 3 straight wins).
export default function StreakBadge({ record }) {
  if (!record || !record.on_streak) return null
  return (
    <span className="streak" title={`${record.win_streak}-game win streak`}>
      <span className="streak-fire">🔥</span>
      <span className="streak-num">{record.win_streak}</span>
    </span>
  )
}
