// Tier pill: a small colored badge showing a player's salary-cap tier.
// S-tier renders an animated gold flame; A is shiny amethyst; B silver,
// C bronze, D plain. Pass `cost` to append the $cost, `size="sm"` for compact.
import { tierClass, tierMeta } from '../tiers.js'

export default function TierBadge({ tier, cost, size, title }) {
  const t = (tier || 'D').toUpperCase()
  const meta = tierMeta(t)
  return (
    <span
      className={`tier-pill ${tierClass(t)} ${size === 'sm' ? 'sm' : ''}`}
      title={title || `${meta.name} tier${cost != null ? ` · cost ${cost}` : ''}`}
    >
      <span className="tier-letter">{meta.label}</span>
      {cost != null && <span className="tier-cost">${cost}</span>}
    </span>
  )
}
