// Draft board: one card per prompt (decade x team). Click a candidate to fill
// that slot. A player already chosen in another slot is disabled (picks must be
// distinct, matching the backend rule).

function StatLine({ p }) {
  return (
    <span className="statline">
      {p.ppg} pts · {p.rpg} reb · {p.apg} ast
    </span>
  )
}

function Candidate({ p, selected, disabled, onPick }) {
  const cls = ['candidate', selected && 'selected', disabled && 'disabled']
    .filter(Boolean)
    .join(' ')
  return (
    <button className={cls} disabled={disabled && !selected} onClick={onPick}>
      <span className="pos-badge">{p.position}</span>
      <span className="cand-name">{p.name}</span>
      <StatLine p={p} />
    </button>
  )
}

export default function DraftBoard({ prompts, picks, onPick, onSubmit, submitting }) {
  const chosenNames = new Set(Object.values(picks))
  const allPicked = prompts.every((p) => picks[p.index])

  return (
    <div className="draft-board">
      <h2>Draft your starting 5</h2>
      <p className="hint">
        One pick per prompt · players must be distinct · opponent is hidden until
        you submit
      </p>

      <div className="prompts">
        {prompts.map((prompt) => {
          const selectedName = picks[prompt.index]
          return (
            <div className="prompt" key={prompt.index}>
              <div className="prompt-head">
                <span className="decade">{prompt.decade}</span>
                <span className="team">{prompt.team}</span>
              </div>
              <div className="candidates">
                {prompt.candidates.map((c) => {
                  const selected = selectedName === c.name
                  const takenElsewhere = chosenNames.has(c.name) && !selected
                  return (
                    <Candidate
                      key={c.name}
                      p={c}
                      selected={selected}
                      disabled={takenElsewhere}
                      onPick={() => onPick(prompt.index, c.name)}
                    />
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      <button
        className="submit"
        disabled={!allPicked || submitting}
        onClick={onSubmit}
      >
        {submitting ? 'Simulating…' : allPicked ? 'Submit Draft ⚔️' : `Pick ${5 - Object.keys(picks).length} more`}
      </button>
    </div>
  )
}
