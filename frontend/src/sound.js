// Lightweight synthesized SFX via the Web Audio API (no audio files).
// The AudioContext is created lazily on first play (after a user gesture like
// clicking Start/PvP), and calls fail silently if audio is blocked.

let ctx = null

function ac() {
  try {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
    if (ctx.state === 'suspended') ctx.resume()
    return ctx
  } catch {
    return null
  }
}

function tone(freq, start, dur, type = 'sine', gain = 0.2) {
  const c = ac()
  if (!c) return
  const t0 = c.currentTime + start
  const osc = c.createOscillator()
  const g = c.createGain()
  osc.type = type
  osc.frequency.value = freq
  osc.connect(g)
  g.connect(c.destination)
  g.gain.setValueAtTime(0.0001, t0)
  g.gain.exponentialRampToValueAtTime(gain, t0 + 0.012)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
  osc.start(t0)
  osc.stop(t0 + dur + 0.03)
}

export function playClash() {
  const c = ac()
  if (!c) return
  tone(130, 0, 0.28, 'sawtooth', 0.35) // low boom
  tone(210, 0, 0.18, 'square', 0.18)
  // short noise burst for "impact"
  const dur = 0.2
  const buf = c.createBuffer(1, Math.floor(c.sampleRate * dur), c.sampleRate)
  const data = buf.getChannelData(0)
  for (let i = 0; i < data.length; i++) {
    data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 2)
  }
  const src = c.createBufferSource()
  const g = c.createGain()
  g.gain.value = 0.25
  src.buffer = buf
  src.connect(g)
  g.connect(c.destination)
  src.start()
}

export function playTick(final = false) {
  tone(final ? 880 : 440, 0, final ? 0.32 : 0.11, 'square', 0.16)
}

export function playPromo() {
  [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.12, 0.28, 'triangle', 0.22))
}
