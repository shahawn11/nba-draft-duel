// Render label for a player record.
//
// display_name is NOT unique (only `username` is the primary key), so two
// guests can both pick the name "Kiro". To disambiguate, append the guest's
// id suffix to their chosen name: "Kiro" -> "Kiro_u86v9sbv".
//
// - Registered users: username is already unique + meaningful -> unchanged.
// - Named guests (display_name differs from their guest_xxx username):
//     -> `${display_name}_${suffix}`
// - Unnamed guests (display_name === username): left as the raw guest_xxx id,
//   so we never produce "guest_xxx_xxx".
const GUEST_PREFIX = 'guest_'

export function nameLabel(record) {
  if (!record) return 'Player'
  const username = record.username || ''
  const display = record.display_name || username
  if (username.startsWith(GUEST_PREFIX)) {
    const suffix = username.slice(GUEST_PREFIX.length)
    if (display && display !== username) return `${display}_${suffix}`
    return username
  }
  return display
}
