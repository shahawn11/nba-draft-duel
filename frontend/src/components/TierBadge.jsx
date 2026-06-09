// Tier pill: a small colored badge showing a player's tier (goat / diamond /
// amethyst / sapphire / gold / silver / bronze / unranked). The tier id is
// taken straight from the backend payload (lowercase). Pass `cost` to append
// the $cost, `size="sm"` for compact.
import { tierClass, tierMeta } from '../tiers.js'

export default function TierBadge({ tier, cost, size, title }) {
  const t = tier || 'unranked'
  const meta = tierMeta(t)
  return (
    <span
      className={`tier-pill ${tierClass(t)} ${size === 'sm' ? 'sm' : ''}`}
      title={title || `${meta.name} tier${cost != null ? ` · cost ${cost}` : ''}`}
    >
      {meta.label && <span className="tier-letter">{meta.label}</span>}
      {cost != null && <span className="tier-cost">${cost}</span>}
    </span>
  )
}
