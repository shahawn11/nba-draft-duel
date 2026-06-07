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

// Achievement avatars — unlocked by accomplishments, not rating.
export const ACHIEVEMENT_AVATARS = [
  { id: 'hot', label: 'Heat Check', how: 'Have a player catch fire (Hot)', ring: '#e8473b' },
  { id: 'slump', label: 'Cold Snap', how: 'Have a player go cold (Slump)', ring: '#4fc3ff' },
  { id: 'fifty', label: 'Bucket Getter', how: 'Have a player score 50', ring: '#ffb01f' },
  { id: 'tripledouble', label: 'Stat Stuffer', how: 'Have a player record a triple-double', ring: '#2bb39a' },
  { id: 'games25', label: 'Regular', how: 'Play 25 games', ring: '#8aa0c0' },
  { id: 'wins100', label: 'Centurion', how: 'Win 100 games', ring: '#ff2d4b' },
]

export const AVATAR_BY_ID = Object.fromEntries(
  [...AVATARS, ...ACHIEVEMENT_AVATARS].map((a) => [a.id, a]),
)

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
    case 'hot': // flame
      return (
        <g stroke="#a8300f" strokeWidth="2.6" strokeLinejoin="round">
          <path d="M50 28 Q40 40 44 50 Q40 48 38 44 Q32 56 38 66 Q44 76 56 74 Q70 70 66 54 Q64 46 58 42 Q60 36 50 28 Z" fill="#ff7a1a" />
          <path d="M50 48 Q44 56 48 64 Q52 70 58 64 Q62 58 56 50 Q54 54 50 48 Z" fill="#ffd23b" stroke="none" />
        </g>
      )
    case 'slump': // ice cube
      return (
        <g stroke="#2a86b8" strokeWidth="2.6" strokeLinejoin="round">
          <path d="M50 30 L70 40 L70 62 L50 72 L30 62 L30 40 Z" fill="#9fe0ff" />
          <path d="M50 30 L50 72 M30 40 L50 50 L70 40 M50 50 L50 72" fill="none" stroke="#5bb8e6" strokeWidth="2" />
          <path d="M37 44 L41 41 M60 56 L64 53" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" />
        </g>
      )
    case 'fifty': // a bucket (slang for buckets) with a ball dropping in
      return (
        <g stroke="#7a3a16" strokeWidth="2.6" strokeLinejoin="round">
          <circle cx="50" cy="36" r="9" fill="#e8743b" />
          <path d="M50 27 V45 M41 36 H59" fill="none" stroke="#7a3a16" strokeWidth="1.8" />
          <path d="M34 48 H66 L62 72 Q50 76 38 72 Z" fill="#c0c6cf" stroke="#5b6270" />
          <path d="M34 48 Q50 54 66 48" fill="none" stroke="#5b6270" strokeWidth="2.4" />
          <text x="50" y="69" textAnchor="middle" fontSize="13" fontWeight="800"
                fill="#2a2f38" stroke="none" fontFamily="system-ui, sans-serif">50</text>
        </g>
      )
    case 'tripledouble': // three stacked stat bars
      return (
        <g stroke="#15705f" strokeWidth="2.4" strokeLinejoin="round">
          <rect x="30" y="36" width="40" height="11" rx="3" fill="#37d6b2" />
          <rect x="30" y="49" width="40" height="11" rx="3" fill="#2bb39a" />
          <rect x="30" y="62" width="40" height="11" rx="3" fill="#1f9080" />
          <text x="62" y="45" textAnchor="middle" fontSize="9" fontWeight="800" fill="#08332b" stroke="none">10</text>
          <text x="62" y="58" textAnchor="middle" fontSize="9" fontWeight="800" fill="#08332b" stroke="none">10</text>
          <text x="62" y="71" textAnchor="middle" fontSize="9" fontWeight="800" fill="#08332b" stroke="none">10</text>
        </g>
      )
    case 'games25': // game clock with "25"
      return (
        <g stroke="#5b6f8f" strokeWidth="3" strokeLinejoin="round">
          <circle cx="50" cy="52" r="20" fill="#1c2330" stroke="#8aa0c0" />
          <text x="50" y="59" textAnchor="middle" fontSize="18" fontWeight="800"
                fill="#cfe0ff" stroke="none" fontFamily="system-ui, sans-serif">25</text>
          <rect x="44" y="28" width="12" height="5" rx="2" fill="#8aa0c0" stroke="none" />
        </g>
      )
    case 'wins100': // the 💯 "hundred points" emoji style
      return (
        <g>
          <text x="50" y="56" textAnchor="middle" fontSize="26" fontWeight="900"
                fill="#ff2d4b" stroke="#b3001e" strokeWidth="0.8"
                fontFamily="system-ui, sans-serif" letterSpacing="-1">100</text>
          <rect x="28" y="62" width="44" height="3.4" rx="1.7" fill="#ff2d4b" />
          <rect x="28" y="68" width="44" height="3.4" rx="1.7" fill="#ff2d4b" />
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
