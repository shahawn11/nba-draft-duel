// Cartoon rank avatars — one per tier, all drawn in the same flat cartoon
// style (circular badge + tinted ring + centered emblem with rounded strokes).
// Pure inline SVG, no asset files. Amateur (brown shirt) is the starter.

export const AVATARS = [
  { id: 'amateur', tier: 'Amateur', label: 'Brown Shirt', min: 0, ring: '#8a5a2b' },
  { id: 'pro', tier: 'Pro', label: 'Basketball', min: 1500, ring: '#e8743b' },
  { id: 'allstar', tier: 'All-Star', label: 'Star', min: 4000, ring: '#2f7fd6' },
  { id: 'veteran', tier: 'Veteran', label: 'Trophy', min: 8000, ring: '#3aa657' },
  { id: 'hof', tier: 'Hall-of-Fame', label: 'Crown', min: 18000, ring: '#7d4fd0' },
  { id: 'goat', tier: 'GOAT', label: 'G.O.A.T.', min: 50000, ring: '#d4af37' },
]

export const AVATAR_BY_ID = Object.fromEntries(AVATARS.map((a) => [a.id, a]))

// Each emblem is drawn inside a 100x100 viewBox, centered ~ (50,52).
function Emblem({ id }) {
  switch (id) {
    case 'amateur': // brown t-shirt / jersey
      return (
        <g stroke="#5e3a18" strokeWidth="3" strokeLinejoin="round">
          <path d="M35 36 L28 44 L34 52 L38 48 L38 70 Q50 74 62 70 L62 48 L66 52 L72 44 L65 36 Q57 42 50 42 Q43 42 35 36 Z" fill="#9c6630" />
          <path d="M42 38 Q50 46 58 38" fill="none" />
        </g>
      )
    case 'pro': // basketball
      return (
        <g>
          <circle cx="50" cy="52" r="20" fill="#e8743b" stroke="#7a3a16" strokeWidth="3" />
          <path d="M50 32 V72 M30 52 H70 M36 38 Q50 52 36 66 M64 38 Q50 52 64 66"
                fill="none" stroke="#7a3a16" strokeWidth="2.6" strokeLinecap="round" />
        </g>
      )
    case 'allstar': // five-point star
      return (
        <path d="M50 30 L57 46 L74 47 L60 58 L65 75 L50 65 L35 75 L40 58 L26 47 L43 46 Z"
              fill="#ffd34d" stroke="#b8881a" strokeWidth="3" strokeLinejoin="round" />
      )
    case 'veteran': // trophy
      return (
        <g stroke="#9a7a12" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round">
          <path d="M38 34 H62 V44 Q62 58 50 60 Q38 58 38 44 Z" fill="#ffd34d" />
          <path d="M38 38 Q28 38 30 48 Q31 53 38 52" fill="none" />
          <path d="M62 38 Q72 38 70 48 Q69 53 62 52" fill="none" />
          <path d="M50 60 V68 M42 72 H58 L56 68 H44 Z" fill="#ffd34d" />
        </g>
      )
    case 'hof': // crown
      return (
        <g stroke="#9a7a12" strokeWidth="3" strokeLinejoin="round">
          <path d="M30 64 L28 40 L40 50 L50 34 L60 50 L72 40 L70 64 Z" fill="#ffd34d" />
          <path d="M30 64 H70" fill="none" />
          <circle cx="28" cy="38" r="3.4" fill="#ff6b6b" stroke="none" />
          <circle cx="50" cy="32" r="3.4" fill="#ff6b6b" stroke="none" />
          <circle cx="72" cy="38" r="3.4" fill="#ff6b6b" stroke="none" />
        </g>
      )
    case 'goat': // goat face
      return (
        <g stroke="#6b6b6b" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round">
          <path d="M34 36 Q30 28 38 30 Q40 38 42 42" fill="#cfcfcf" />
          <path d="M66 36 Q70 28 62 30 Q60 38 58 42" fill="#cfcfcf" />
          <path d="M38 42 Q50 36 62 42 Q68 54 58 66 Q50 72 42 66 Q32 54 38 42 Z" fill="#eaeaea" />
          <circle cx="44" cy="52" r="2.6" fill="#333" stroke="none" />
          <circle cx="56" cy="52" r="2.6" fill="#333" stroke="none" />
          <path d="M46 62 Q50 65 54 62" fill="none" />
          <path d="M44 66 Q42 72 46 72 M56 66 Q58 72 54 72" fill="#eaeaea" />
        </g>
      )
    default:
      return null
  }
}

export default function Avatar({ id = 'amateur', size = 40, locked = false, ring }) {
  const meta = AVATAR_BY_ID[id] || AVATAR_BY_ID.amateur
  const ringColor = ring || meta.ring
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={`avatar${locked ? ' locked' : ''}`}
         role="img" aria-label={`${meta.tier} avatar`}>
      <circle cx="50" cy="50" r="48" fill="#1c2230" stroke={ringColor} strokeWidth="4" />
      <circle cx="50" cy="50" r="40" fill="#2a3142" />
      <Emblem id={id} />
      {locked && (
        <g>
          <rect x="0" y="0" width="100" height="100" rx="50" fill="rgba(10,12,18,0.62)" />
          <path d="M42 50 V44 a8 8 0 0 1 16 0 V50" fill="none" stroke="#cfd6e4" strokeWidth="4" strokeLinecap="round" />
          <rect x="38" y="50" width="24" height="18" rx="3" fill="#cfd6e4" />
        </g>
      )}
    </svg>
  )
}
