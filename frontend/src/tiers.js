// Salary-cap tier metadata — mirrors backend rating.CAP_TIERS.
// Each draftable player belongs to a tier (by their 0-100 rating); the tier
// drives both the flat cost and the visual treatment on the card.
//   S — gold, animated flame   A — amethyst (shiny)
//   B — silver                 C — bronze                 D — plain
export const TIERS = {
  S: { label: '💎', cost: 80, name: 'Diamond' },
  A: { label: 'A', cost: 62, name: 'All-Star' },
  B: { label: 'B', cost: 50, name: 'Starter' },
  C: { label: 'C', cost: 38, name: 'Rotation' },
  D: { label: 'D', cost: 28, name: 'Role player' },
}

export function tierMeta(tier) {
  return TIERS[tier] || TIERS.D
}

// Class used to color a tier pill / card accent, e.g. `tier-S`.
export function tierClass(tier) {
  return `tier-${(tier || 'D').toUpperCase()}`
}
