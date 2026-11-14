/**
 * Charts (brief §5b B-D). Recharts for the line and stacked-bar charts; plain HTML for attainment bars.
 * Colours come from the design tokens at runtime (SVG attributes cannot read CSS variables), so charts follow
 * light / dark / high-contrast. The red threshold line is always --margin. Every chart has a title (from its
 * card), axis labels, a legend when needed, tooltips and a short text summary for screen readers.
 */
import { useEffect, useState } from 'react'
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Segmented } from './Kit'
import { band } from './status'

const TOKENS = ['--action', '--margin', '--good', '--near', '--bad', '--ink', '--ink-soft', '--ink-faint', '--rule', '--rule-soft', '--sheet', '--action-tint', '--good-bg'] as const
type Tok = Record<(typeof TOKENS)[number], string>

function readTokens(): Tok {
  const cs = getComputedStyle(document.documentElement)
  return Object.fromEntries(TOKENS.map((t) => [t, cs.getPropertyValue(t).trim()])) as Tok
}
/** Token values, re-read when the theme / contrast / colour-scheme changes. */
function useTokens(): Tok {
  const [t, setT] = useState<Tok>(readTokens)
  useEffect(() => {
    const update = () => setT(readTokens())
    const mo = new MutationObserver(update)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-contrast'] })
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    mq?.addEventListener?.('change', update)
    return () => { mo.disconnect(); mq?.removeEventListener?.('change', update) }
  }, [])
  return t
}
const reduced = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/* ── B. Mastery over time ──────────────────────────────────────────────────────────────────────────────── */
/** score = mastery after this attempt (null on the diagnostic point); attemptScore = this quiz's own score;
 *  readiness = diagnostic result (not part of mastery). */
export type MasteryPoint = { label: string; date: string; activity: string; score: number | null; attemptScore?: number; readiness?: number; detail?: string; event?: string }
export type CloSeries = { clo: string; description: string; threshold: number; points: MasteryPoint[] }

function statusColor(t: Tok, score: number, threshold: number) {
  const b = band(score, threshold)
  return b === 'attained' ? t['--good'] : b === 'near' ? t['--near'] : t['--bad']
}

function MasteryTooltip({ active, payload, threshold }: { active?: boolean; payload?: { payload: MasteryPoint }[]; threshold: number }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  if (p.score == null) {
    return <div className="ctip"><strong>Diagnostic</strong><span>Readiness {p.readiness}% · sets your starting point, not counted in mastery</span></div>
  }
  const b = band(p.score, threshold)
  return (
    <div className="ctip">
      <strong>{p.activity}{p.date ? ` · ${p.date}` : ''}</strong>
      <span>This quiz: {p.attemptScore}%{p.detail ? ` (${p.detail})` : ''}</span>
      <span>Mastery now {p.score}% (best of your last 3) · {b === 'attained' ? 'attained' : b === 'near' ? 'close to target' : 'below target'}</span>
    </div>
  )
}

export function MasteryLine({ series, height = 300, compact }: { series: CloSeries; height?: number; compact?: boolean }) {
  const t = useTokens()
  const { threshold, points } = series
  const Dot = (props: { cx?: number; cy?: number; payload?: MasteryPoint }) => {
    const { cx, cy, payload } = props
    if (cx == null || cy == null || !payload || payload.score == null) return null
    return <circle cx={cx} cy={cy} r={compact ? 3 : 6} fill={t['--sheet']} stroke={statusColor(t, payload.score, threshold)} strokeWidth={compact ? 2 : 3} />
  }
  // the diagnostic is a separate marker (a square), not the start of the mastery line
  const DiagDot = (props: { cx?: number; cy?: number; payload?: MasteryPoint }) => {
    const { cx, cy, payload } = props
    if (cx == null || cy == null || payload?.readiness == null) return null
    const r = compact ? 3 : 5
    return <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} fill={t['--sheet']} stroke={t['--ink-soft']} strokeWidth={2} />
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={points} margin={compact ? { top: 6, right: 6, bottom: 0, left: 6 } : { top: 28, right: 24, bottom: 8, left: 0 }}>
        {!compact && <CartesianGrid stroke={t['--rule-soft']} vertical={false} />}
        <ReferenceArea y1={threshold} y2={100} fill={t['--good-bg']} fillOpacity={0.3} ifOverflow="hidden" />
        <Area type="linear" dataKey="score" baseValue={0} fill={t['--action']} fillOpacity={compact ? 0.12 : 0.1} stroke="none" connectNulls={false}
          isAnimationActive={!reduced()} animationDuration={500} activeDot={false} />
        <XAxis dataKey="label" hide={compact} padding={compact ? { left: 6, right: 6 } : { left: 28, right: 28 }} tick={{ fill: t['--ink-soft'], fontSize: 12 }} tickLine={false} axisLine={{ stroke: t['--rule'] }}
          label={compact ? undefined : { value: 'Attempt', position: 'insideBottomRight', offset: -4, fill: t['--ink-soft'], fontSize: 12 }} />
        <YAxis domain={[0, 100]} ticks={[0, 20, 40, 60, 80, 100]} hide={compact} tick={{ fill: t['--ink-soft'], fontSize: 12 }} tickLine={false} axisLine={false} width={40}
          label={compact ? undefined : { value: 'Mastery %', angle: -90, position: 'insideLeft', fill: t['--ink-soft'], fontSize: 12 }} />
        <ReferenceLine y={threshold} stroke={t['--margin']} strokeDasharray="6 4" strokeWidth={2}
          label={compact ? undefined : { value: `Target ${threshold}%`, position: 'insideTopLeft', fill: t['--margin'], fontSize: 13, fontWeight: 700 }} />
        {!compact && points.filter((p) => p.event).map((p) => (
          <ReferenceLine key={p.label} x={p.label} stroke={t['--ink-faint']} strokeDasharray="3 3" label={{ value: p.event, position: 'top', fill: t['--ink'], fontSize: 12 }} />
        ))}
        {!compact && <Tooltip content={<MasteryTooltip threshold={threshold} />} cursor={{ stroke: t['--ink-faint'] }} />}
        <Line type="linear" dataKey="score" stroke={t['--action']} strokeWidth={compact ? 2 : 3} dot={<Dot />} activeDot={false} connectNulls={false}
          isAnimationActive={!reduced()} animationDuration={500}
          label={compact ? undefined : { position: 'top', fill: t['--ink'], fontSize: 12, formatter: (v: unknown) => (v == null ? '' : `${v}%`) }} />
        <Line type="linear" dataKey="readiness" stroke="none" dot={<DiagDot />} activeDot={false} isAnimationActive={false}
          label={compact ? undefined : { position: 'top', fill: t['--ink-soft'], fontSize: 12, formatter: (v: unknown) => (v == null ? '' : `${v}%`) }} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function lineSummary(s: CloSeries) {
  const diag = s.points.find((p) => p.readiness != null)?.readiness
  const att = s.points.filter((p) => p.score != null) as (MasteryPoint & { score: number })[]
  const start = diag != null ? `Diagnostic readiness ${diag}%. ` : ''
  if (!att.length) return `${start}No formative quizzes yet for ${s.clo}, so there is no mastery score yet.`
  const last = att[att.length - 1]
  const passed = att.find((p) => p.score >= s.threshold)
  return `${start}${s.clo} mastery is ${last.score}% after ${att.length} quiz${att.length === 1 ? '' : 'zes'} (best of the last 3)`
    + (passed ? `; it reached the ${s.threshold}% target at ${passed.label}.` : `; the ${s.threshold}% target is not reached yet.`)
}

/** One large chart with a CLO selector (learner page / course page). */
export function MasteryOverTime({ series }: { series: CloSeries[] }) {
  const [clo, setClo] = useState(series[0]?.clo ?? '')
  const s = series.find((x) => x.clo === clo) ?? series[0]
  if (!s) return <p className="kempty">No attempts yet — take the diagnostic to see your progress.</p>
  return (
    <div className="chart-block">
      <div className="chart-bar">
        <p className="chart-sub">{s.clo} · {s.description}</p>
        <Segmented chips label="Outcome" options={series.map((x) => ({ value: x.clo, label: x.clo }))} value={s.clo} onChange={setClo} />
      </div>
      {s.points.length ? <MasteryLine series={s} /> : <p className="kempty">No attempts yet for {s.clo}.</p>}
      {s.points.some((p) => p.readiness != null) && <p className="chart-note small">Square = diagnostic readiness (your starting point, not part of mastery). Line = mastery after each quiz: the best of your last 3.</p>}
      <p className="chart-summary">{lineSummary(s)}</p>
    </div>
  )
}

/** Small multiples: one mini chart per CLO (progress page). */
export function MasteryMultiples({ series }: { series: CloSeries[] }) {
  return (
    <ul className="multiples">
      {series.map((s) => {
        const last = [...s.points].reverse().find((p) => p.score != null)?.score
        return (
          <li key={s.clo} className="multiple">
            <div className="multiple-head"><strong>{s.clo}</strong><span className="tabular">{last == null ? '—' : `${last}%`}</span></div>
            {s.points.length ? <MasteryLine series={s} height={72} compact /> : <p className="kempty small">No attempts yet</p>}
            <p className="sr-only">{lineSummary(s)}</p>
          </li>
        )
      })}
    </ul>
  )
}

/* ── D. Where students are on the path (stacked: on track / in reteach / escalated) ───────────────────── */
export type StepCount = { step: string; unit: string; onTrack: number; reteach: number; escalated: number }

export function PathDistribution({ data, onSelect, withoutPath = 0 }: { data: StepCount[]; onSelect?: (s: StepCount) => void; withoutPath?: number }) {
  const t = useTokens()
  const total = (d: StepCount) => d.onTrack + d.reteach + d.escalated
  const worst = data.reduce<StepCount | null>((m, d) => (!m || d.reteach + d.escalated > m.reteach + m.escalated ? d : m), null)
  const units = [...new Set(data.map((d) => d.unit))]
  const busiestUnit = units.map((u) => [u, data.filter((d) => d.unit === u).reduce((s, d) => s + total(d), 0)] as const).sort((a, b) => b[1] - a[1])[0]
  const summary = !data.length ? 'No students on the path yet.'
    : `Most students are ${units.length > 1 && !/path|finished/i.test(busiestUnit[0]) ? `in ${busiestUnit[0]}` : `at ${[...data].sort((x, y) => total(y) - total(x))[0].step}`}.` + (worst && worst.reteach + worst.escalated
      ? ` ${worst.reteach} in reteach and ${worst.escalated} escalated at ${worst.step}.` : ' Nobody is in reteach or escalated.')
    + (withoutPath ? ` ${withoutPath} student${withoutPath === 1 ? ' has' : 's have'} no path yet (diagnostic not taken) and ${withoutPath === 1 ? 'is' : 'are'} not shown.` : '')
  return (
    <div className="chart-block">
      <ul className="legend-row" aria-label="Legend">
        <li><span className="sw sw-action" aria-hidden="true" />On track</li>
        <li><span className="sw sw-near" aria-hidden="true" />In reteach</li>
        <li><span className="sw sw-bad" aria-hidden="true" />Escalated</li>
      </ul>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 28, right: 8, bottom: 8, left: 0 }} barCategoryGap="28%">
          <CartesianGrid stroke={t['--rule-soft']} vertical={false} />
          <XAxis dataKey="step" tick={{ fill: t['--ink-soft'], fontSize: 12 }} tickLine={false} axisLine={{ stroke: t['--rule'] }} />
          <YAxis allowDecimals={false} domain={[0, (max: number) => Math.max(1, max)]} tick={{ fill: t['--ink-soft'], fontSize: 12 }} tickLine={false} axisLine={false} width={32}
            label={{ value: 'Students', angle: -90, position: 'insideLeft', fill: t['--ink-soft'], fontSize: 12 }} />
          {worst && data.length > 1 && worst.reteach + worst.escalated > 0 && (
            <ReferenceArea x1={worst.step} x2={worst.step} stroke={t['--margin']} strokeDasharray="4 3" fill="none" ifOverflow="extendDomain"
              label={{ value: 'Bottleneck', position: 'top', fill: t['--margin'], fontSize: 12, fontWeight: 700 }} />
          )}
          <Tooltip cursor={{ fill: t['--action-tint'] }} content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as StepCount
            return <div className="ctip"><strong>{d.step} · {d.unit}</strong><span>{d.onTrack} on track · {d.reteach} in reteach · {d.escalated} escalated</span></div>
          }} />
          <Bar dataKey="onTrack" stackId="s" fill={t['--action']} isAnimationActive={!reduced()} onClick={(_, i) => onSelect?.(data[i])} />
          <Bar dataKey="reteach" stackId="s" fill={t['--near']} isAnimationActive={!reduced()} onClick={(_, i) => onSelect?.(data[i])} />
          <Bar dataKey="escalated" stackId="s" fill={t['--bad']} radius={[4, 4, 0, 0]} isAnimationActive={!reduced()} onClick={(_, i) => onSelect?.(data[i])}
            label={{ position: 'top', fill: t['--ink'], fontSize: 12, fontWeight: 700, formatter: (_v: unknown, _n?: unknown, i?: number) => (i != null ? String(total(data[i])) : '') }}>
            {data.map((d) => <Cell key={d.step} cursor={onSelect ? 'pointer' : undefined} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <ul className="unit-axis" aria-hidden="true">{units.map((u) => <li key={u} style={{ flexGrow: data.filter((d) => d.unit === u).length }}>{u}</li>)}</ul>
      <p className="chart-summary">{summary}</p>
    </div>
  )
}

/* ── D. Attainment by outcome: share of students in each status, average on the right (plain HTML) ────── */
export type AttainmentRow = { clo: string; name: string; attained: number; near: number; notAttained: number; insufficient: number; average: number | null; threshold: number; assessed?: number }

export function AttainmentByOutcome({ rows }: { rows: AttainmentRow[] }) {
  const near = rows[0] ? `${rows[0].threshold - 15}–${rows[0].threshold - 1}%` : ''
  const parts = (r: AttainmentRow) => [['attained', r.attained, 'Attained'], ['near', r.near, 'Near'], ['bad', r.notAttained, 'Not attained'], ['none', r.insufficient, 'Not enough evidence']] as const
  return (
    <div className="chart-block">
      <ul className="att-list">
        {rows.map((r) => (
          <li key={r.clo} className="att-row">
            <div className="att-name"><strong>{r.clo}</strong><span>{r.name}</span></div>
            <div className="att-bar" role="img" aria-label={`${r.clo}: ${parts(r).map(([, v, l]) => `${v}% ${l.toLowerCase()}`).join(', ')}`}>
              {parts(r).map(([k, v, l]) => v > 0 && <span key={k} className={`att-seg att-${k}`} style={{ flexGrow: v }} title={`${l}: ${v}%`}>{v >= 9 ? `${v}%` : ''}</span>)}
            </div>
            <div className="att-avg tabular"><strong>{r.average == null ? '—' : `${r.average}%`}</strong><span>{r.average == null ? 'no scores yet' : `avg of ${r.assessed ?? '?'} student${r.assessed === 1 ? '' : 's'}${r.average >= r.threshold ? ' ✓' : ''}`}</span></div>
          </li>
        ))}
      </ul>
      <ul className="legend-row" aria-label="Legend">
        <li><span className="sw att-attained" aria-hidden="true" />Attained (≥ {rows[0]?.threshold ?? 60}%)</li>
        <li><span className="sw att-near" aria-hidden="true" />Near ({near})</li>
        <li><span className="sw att-bad" aria-hidden="true" />Not attained</li>
        <li><span className="sw att-none" aria-hidden="true" />Not enough evidence</li>
      </ul>
    </div>
  )
}
