// Salary-cap / duel tier metadata — mirrors backend rating.CAP_TIERS (the 8
// named bands on the blended 0-100 overall). Each draftable player belongs to a
// tier (by their rating); the tier drives the flat cost and the card visual.
//   goat — legendary gold      diamond  — icy blue
//   amethyst — purple          sapphire — deep blue
//   gold — warm gold           silver   — steel
//   bronze — copper            unranked — plain
// Tier ids are lowercase and match the backend payload's `tier` field exactly.
export const TIERS = {
  goat:     { label: '👑', cost: 82, name: 'GOAT' },
  diamond:  { label: '💎', cost: 75, name: 'Diamond' },
  amethyst: { label: '🔮', cost: 63, name: 'Amethyst' },
  sapphire: { label: '🔷', cost: 54, name: 'Sapphire' },
  gold:     { label: '', cost: 46, name: 'Gold' },
  silver:   { label: '', cost: 40, name: 'Silver' },
  bronze:   { label: '', cost: 34, name: 'Bronze' },
  unranked: { label: '–',  cost: 28, name: 'Unranked' },
}

export function tierMeta(tier) {
  return TIERS[tier] || TIERS.unranked
}

// Class used to color a tier pill / card accent, e.g. `tier-goat`.
export function tierClass(tier) {
  return `tier-${tier || 'unranked'}`
}
