// Ambient looping background music for the draft, synthesized with the Web
// Audio API (no audio files). A gentle A-minor pentatonic melody over a
// root/fifth drone — consonant by construction, kept quiet so it's background.
import { isMuted, onMuteChange } from './audio.js'

let ctx = null
let master = null
let timer = null
let step = 0
let nextTime = 0
let playing = false
let wantPlaying = false

const STEP = 0.22 // seconds per step
// A-minor pentatonic melody (A C D E G across octaves) — 16 steps.
const MEL = [
  440.0, 523.25, 587.33, 659.25,
  523.25, 440.0, 329.63, 392.0,
  440.0, 523.25, 659.25, 783.99,
  587.33, 523.25, 440.0, 392.0,
]
const BASS = [110.0, 164.81] // A2 / E3 drone, one every 8 steps

function ensure() {
  try {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
    if (ctx.state === 'suspended') ctx.resume()
    return ctx
  } catch {
    return null
  }
}

function note(freq, t, dur, type, gain) {
  const osc = ctx.createOscillator()
  const g = ctx.createGain()
  osc.type = type
  osc.frequency.value = freq
  osc.connect(g)
  g.connect(master)
  g.gain.setValueAtTime(0.0001, t)
  g.gain.exponentialRampToValueAtTime(gain, t + 0.03)
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  osc.start(t)
  osc.stop(t + dur + 0.03)
}

function scheduler() {
  if (!playing) return
  while (nextTime < ctx.currentTime + 0.25) {
    const i = step % MEL.length
    note(MEL[i], nextTime, 0.2, 'triangle', 0.05)
    if (i % 8 === 0) note(BASS[(step / 8) % BASS.length | 0], nextTime, 1.7, 'sine', 0.06)
    nextTime += STEP
    step += 1
  }
}

function _start() {
  const c = ensure()
  if (!c || playing) return
  master = c.createGain()
  master.gain.setValueAtTime(0.0001, c.currentTime)
  master.gain.exponentialRampToValueAtTime(0.7, c.currentTime + 0.8) // fade in
  master.connect(c.destination)
  playing = true
  step = 0
  nextTime = c.currentTime + 0.1
  timer = setInterval(scheduler, 60)
}

function _stop() {
  if (!playing) return
  playing = false
  if (timer) { clearInterval(timer); timer = null }
  try {
    const now = ctx.currentTime
    master.gain.cancelScheduledValues(now)
    master.gain.setValueAtTime(master.gain.value, now)
    master.gain.exponentialRampToValueAtTime(0.0001, now + 0.4) // fade out
    const m = master
    setTimeout(() => { try { m.disconnect() } catch { /* */ } }, 600)
  } catch { /* */ }
}

export function startMusic() {
  wantPlaying = true
  if (!isMuted()) _start()
}

export function stopMusic() {
  wantPlaying = false
  _stop()
}

// React to the mute toggle while a draft is in progress.
onMuteChange((muted) => {
  if (muted) _stop()
  else if (wantPlaying) _start()
})
