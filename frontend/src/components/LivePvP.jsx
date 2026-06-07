import { useState, useEffect, useRef, useCallback } from 'react'
import DraftBoard from './DraftBoard.jsx'
import Results from './Results.jsx'
import MatchIntro from './MatchIntro.jsx'
import { wsBaseUrl } from '../api.js'

const SLOTS = ['PG', 'SG', 'SF', 'PF', 'C']

function wsUrl(username, token, displayName) {
  const t = token ? `&token=${encodeURIComponent(token)}` : ''
  const d = displayName ? `&display_name=${encodeURIComponent(displayName)}` : ''
  return `${wsBaseUrl()}/ws/pvp?username=${encodeURIComponent(username)}${t}${d}`
}

export default function LivePvP({ username, token, displayName, onExit, onRecord, meRecord, onActive }) {
  const [status, setStatus] = useState('connecting') // connecting|waiting|drafting|result|left|error
  const [opponent, setOpponent] = useState('')
  const [opponentRecord, setOpponentRecord] = useState(null)
  const [step, setStep] = useState(null)
  const [deadline, setDeadline] = useState(0)
  const [filled, setFilled] = useState([])
  const [picksMade, setPicksMade] = useState(0)
  const [opponentPicks, setOpponentPicks] = useState(0)
  const [waitingForOpp, setWaitingForOpp] = useState(false)
  const roundRef = useRef(0)
  const [result, setResult] = useState(null)
  const [record, setRecord] = useState(null)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const wsRef = useRef(null)
  const terminalRef = useRef(false)   // true once the match has finished (result/left)
  const [nonce, setNonce] = useState(0) // bump to reconnect

  const connect = useCallback(() => {
    setStatus('connecting'); setResult(null); setFilled([]); setPicksMade(0)
    setOpponentPicks(0); setWaitingForOpp(false); setError(''); terminalRef.current = false
    const ws = new WebSocket(wsUrl(username, token, displayName))
    wsRef.current = ws
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data)
      switch (m.type) {
        case 'waiting': setStatus('waiting'); break
        case 'matched': setOpponent(m.opponent); setOpponentRecord(m.opponent_record || null); setStatus('intro'); break
        case 'round':
          roundRef.current = m.round
          setStep(m.current_step); setDeadline(m.deadline)
          setPicksMade(m.picks_made); setWaitingForOpp(false); setStatus('drafting')
          break
        case 'picked_ok':
        case 'auto_picked':
          setFilled(m.filled || []); if (m.picks_made != null) setPicksMade(m.picks_made)
          setWaitingForOpp(true)
          if (m.type === 'auto_picked' && m.player) {
            setToast(`⏱ Time! Auto-drafted ${m.player}${m.slot ? ` at ${m.slot}` : ''}`)
          }
          break
        case 'opponent_progress': setOpponentPicks(m.picks_made); break
        case 'error': setError(m.detail); setWaitingForOpp(false); break
        case 'result':
          terminalRef.current = true
          setResult(m.result); setRecord(m.result.record); setStatus('result'); setError('')
          if (onRecord && m.result.record) onRecord(m.result.record)
          break
        case 'opponent_left':
          terminalRef.current = true
          setRecord(m.record); setStatus('left'); setError('')
          if (onRecord && m.record) onRecord(m.record)
          break
        default: break
      }
    }
    // Mobile browsers fire onerror/onclose on a NORMAL close (e.g. the server
    // closing after the result). Only surface an error if the match hasn't
    // already finished.
    ws.onerror = () => { if (!terminalRef.current) setError('connection error') }
    ws.onclose = () => { if (!terminalRef.current && statusRef.current === 'connecting') setStatus('error') }
  }, [username, token, displayName, onRecord])
  // keep a ref of status for onclose
  const statusRef = useRef(status)
  useEffect(() => { statusRef.current = status }, [status])
  // Tell the parent whether a match is in progress (so leaving warns only then).
  useEffect(() => {
    const active = ['connecting', 'waiting', 'intro', 'drafting'].includes(status)
    if (onActive) onActive(active)
  }, [status])

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(''), 3500)
    return () => clearTimeout(id)
  }, [toast])

  useEffect(() => {
    connect()
    return () => { try { wsRef.current && wsRef.current.close() } catch { /* */ } }
  }, [connect, nonce])

  function pick(name, slot) {
    setWaitingForOpp(true)
    try { wsRef.current.send(JSON.stringify({ type: 'pick', round: roundRef.current, player_name: name, slot })) } catch { /* */ }
  }

  const openSlots = SLOTS.filter((s) => !filled.some((f) => f.slot === s))
  const view = step && {
    current_step: step, filled, open_slots: openSlots,
    picks_made: picksMade, total_slots: SLOTS.length,
  }

  return (
    <div className="live">
      {error && <div className="error">{error}</div>}
      {toast && <div className="toast">{toast}</div>}

      {(status === 'connecting' || status === 'waiting') && (
        <div className="waiting-room">
          <div className="spinner" />
          <h2>{status === 'connecting' ? 'Connecting…' : 'Finding an opponent…'}</h2>
          <p className="hint">PvP — you'll draft head-to-head on a 10s-per-pick clock.</p>
          <button className="btn-cancel modal-actions" onClick={onExit}>Cancel</button>
        </div>
      )}

      {status === 'intro' && (
        <MatchIntro me={displayName || username} meRecord={meRecord} opponent={(opponentRecord && opponentRecord.display_name) || opponent} opponentRecord={opponentRecord} />
      )}

      {status === 'drafting' && view && (
        <>
          <div className="live-banner">
            ⚔️ Live vs <b>{(opponentRecord && opponentRecord.display_name) || opponent || 'opponent'}</b>
            {opponentRecord && (
              <span className="opp-rec">
                {' '}— <span className={`tier-badge ${(opponentRecord.tier || '').toLowerCase().replace(/[^a-z]/g, '')}`}>{opponentRecord.tier}</span>
                {' '}<b>{opponentRecord.rating}</b> · {opponentRecord.wins}W-{opponentRecord.losses}L
              </span>
            )}
          </div>
          <DraftBoard
            view={view}
            onPick={pick}
            deadline={deadline}
            waiting={waitingForOpp}
            opponentPicks={opponentPicks}
          />
        </>
      )}

      {status === 'result' && result && (
        <Results result={result} onPlayAgain={() => setNonce((n) => n + 1)} />
      )}

      {status === 'left' && (
        <div className="waiting-room">
          <h2 className="banner win" style={{ padding: '18px 24px' }}>Opponent left — you win! 🏆</h2>
          {record && <p className="hint">Record: {record.wins}W · {record.losses}L</p>}
          <button className="submit" onClick={() => setNonce((n) => n + 1)}>Find new match</button>
          <button className="btn-cancel" style={{ marginTop: 8 }} onClick={onExit}>Back</button>
        </div>
      )}
    </div>
  )
}
