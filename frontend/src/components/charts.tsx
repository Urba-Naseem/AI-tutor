/**
 * Small, dependency-free charts (DESIGN.md + the dataviz rules): thin marks with 4px rounded data-ends, a 2px gap
 * between segments, values in text tokens (never the mark colour), a legend when there are two or more series,
 * and every chart readable without colour - status keeps its icon + label, and each chart has a text equivalent
 * (accessible name, visible numbers, or the list it summarises).
 */
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from './ui'

type Tone = 'primary' | 'ok' | 'warn' | 'bad' | 'info'

/** Stat tile: icon chip, label, value, optional sub-line (DESIGN.md "Figures - when the form is a number"). */
export function StatTile({ icon: Icon, label, value, sub, tone = 'primary', children }: { icon: LucideIcon; label: string; value: ReactNode; sub?: ReactNode; tone?: Tone; children?: ReactNode }) {
  return (
    <div className="tile">
      <span className={`tile-icon${tone === 'primary' ? '' : ` ${tone}`}`} aria-hidden="true"><Icon className="icon" /></span>
      <div className="tile-body">
        <p className="tile-label">{label}</p>
        <p className="tile-value">{value}</p>
        {sub && <p className="tile-sub">{sub}</p>}
        {children}
      </div>
    </div>
  )
}

/** Progress ring for one headline share (e.g. "30% of the path done"). */
export function Ring({ value, label, caption, size = 112, stroke = 10, done }: { value: number; label: string; caption?: string; size?: number; stroke?: number; done?: boolean }) {
  const v = Math.max(0, Math.min(100, value))
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="ring" role="img" aria-label={`${label}: ${Math.round(v)}%`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        {v > 0 && (
          <circle className={`ring-fill${done ? ' ok' : ''}`} cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} />
        )}
      </svg>
      <span className="ring-center" aria-hidden="true">
        <span className="ring-value">{Math.round(v)}%</span>
        {caption && <span className="ring-cap">{caption}</span>}
      </span>
    </div>
  )
}

export type ChartStep = { id: number; position: number; unit_number: number; unit_title: string; label: string; clo_code: string; status: string }

/** Learning path at a glance: one segmented bar per unit (a segment per step: done / up next / not started). */
export function PathChart({ steps, nextId }: { steps: ChartStep[]; nextId: number | null }) {
  const units: { number: number; title: string; steps: ChartStep[] }[] = []
  for (const s of steps) {
    const last = units[units.length - 1]
    if (last && last.number === s.unit_number) last.steps.push(s)
    else units.push({ number: s.unit_number, title: s.unit_title, steps: [s] })
  }
  const done = steps.filter((s) => s.status === 'done').length
  const state = (s: ChartStep) => (s.status === 'done' ? 'done' : s.id === nextId ? 'next' : 'todo')
  const word = { done: 'done', next: 'up next', todo: 'not started' } as const
  return (
    <figure className="m-0" aria-label={`Learning path: ${done} of ${steps.length} steps done${nextId ? ', 1 up next' : ''}, across ${units.length} units`}>
      <ul className="legend" aria-label="Legend">
        <li><span className="swatch done" aria-hidden="true" />Done <strong>{done}</strong></li>
        {nextId && <li><span className="swatch next" aria-hidden="true" />Up next <strong>1</strong></li>}
        <li><span className="swatch" aria-hidden="true" />Not started <strong>{steps.length - done - (nextId ? 1 : 0)}</strong></li>
      </ul>
      <ul className="pathchart">
        {units.map((u) => {
          const d = u.steps.filter((s) => s.status === 'done').length
          return (
            <li key={`${u.number}-${u.steps[0].id}`}>
              <span className="pathchart-unit" title={`Unit ${u.number}: ${u.title}`}><span>Unit {u.number} · </span>{u.title}</span>
              <span className="segs" role="img" aria-label={`Unit ${u.number}: ${d} of ${u.steps.length} steps done`}>
                {u.steps.map((s) => <span key={s.id} className={`seg ${state(s)}`} title={`${s.position}. ${s.label} (${s.clo_code}) - ${word[state(s)]}`} />)}
              </span>
              <span className="pathchart-count">{d} / {u.steps.length}</span>
            </li>
          )
        })}
      </ul>
    </figure>
  )
}

export type MasteryRow = { clo_id: number; clo_code: string; description: string; threshold: number; mastery_pct: number | null; attained: boolean; status: string; attempts: number }

/** Mastery by outcome: a bar per CLO (value at the tip), the target as a marker, and a status badge (icon + text). */
export function MasteryChart({ rows, compact }: { rows: MasteryRow[]; compact?: boolean }) {
  const targets = [...new Set(rows.map((r) => r.threshold))]
  return (
    <>
      <ul className="legend" aria-label="Legend">
        <li><span className="swatch done" aria-hidden="true" />At or above target</li>
        <li><span className="swatch low" aria-hidden="true" />Below target</li>
        <li><span className="swatch target" aria-hidden="true" />Target{targets.length === 1 ? ` ${targets[0]}%` : ''}</li>
      </ul>
      <ul className="mchart">
        {rows.map((r) => {
          const ok = r.mastery_pct !== null && r.mastery_pct >= r.threshold
          return (
            <li key={r.clo_id}>
              <div className="mchart-label">
                <strong>{r.clo_code}</strong><span className="desc">{r.description}</span>
                {!compact && <div className="mchart-meta">{r.attempts} attempt{r.attempts === 1 ? '' : 's'}</div>}
              </div>
              <div className="mchart-plot">
                {r.mastery_pct === null ? <span className="mchart-none">Not assessed yet</span> : (
                  <>
                    <span className="mchart-track" role="img" aria-label={`${r.clo_code}: ${r.mastery_pct}% mastery, target ${r.threshold}%`}>
                      <span className={`mchart-fill${ok ? ' ok' : ''}`} style={{ display: 'block', width: `${Math.max(2, Math.min(100, r.mastery_pct))}%` }} />
                      <span className="mchart-target" style={{ left: `${r.threshold}%` }} title={`Target ${r.threshold}%`} />
                    </span>
                    <span className="mchart-value" aria-hidden="true">{Math.round(r.mastery_pct)}%</span>
                  </>
                )}
              </div>
              <div className="mchart-status"><Badge value={r.mastery_pct === null && r.status !== 'attained' ? 'not_started' : r.status} /></div>
            </li>
          )
        })}
      </ul>
    </>
  )
}
