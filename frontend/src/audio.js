// Shared audio on/off state for SFX + music. Persisted to localStorage so the
// choice sticks across sessions. Modules subscribe to react to changes.

let muted = false
try { muted = localStorage.getItem('ndd_muted') === '1' } catch { /* */ }

const subs = new Set()

export function isMuted() {
  return muted
}

export function setMuted(v) {
  muted = !!v
  try { localStorage.setItem('ndd_muted', muted ? '1' : '0') } catch { /* */ }
  subs.forEach((fn) => fn(muted))
}

export function toggleMuted() {
  setMuted(!muted)
  return muted
}

export function onMuteChange(fn) {
  subs.add(fn)
  return () => subs.delete(fn)
}
