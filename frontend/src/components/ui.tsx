import { AlertCircle, AlertTriangle, CheckCircle2, Circle, Clock, Info, Pencil, RotateCcw, XCircle, type LucideIcon } from 'lucide-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { toast } from './toast'

type AlertKind = 'error' | 'success' | 'info' | 'warning'
const ALERT_ICON: Record<AlertKind, LucideIcon> = { error: AlertCircle, success: CheckCircle2, info: Info, warning: AlertTriangle }
const ALERT_TITLE: Record<AlertKind, string> = { error: 'Something went wrong', success: 'Done', info: 'Please note', warning: 'Check this' }

/**
 * Inline alert (DESIGN.md §5): icon + title + text. Errors are announced (role="alert").
 * Pass `onRetry` for load errors to get the §7 error design ("Try again" + where to get help).
 */
export function Alert({ kind = 'error', children, id, title, onRetry }: { kind?: AlertKind; children: ReactNode; id?: string; title?: string; onRetry?: () => void }) {
  if (!children) return null
  const Icon = ALERT_ICON[kind]
  return (
    <div id={id} className={`alert ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon className="icon" aria-hidden="true" />
      <div>
        <strong className="alert-title">{title ?? (onRetry ? "We couldn't load this" : ALERT_TITLE[kind])}</strong>
        <div>{children}</div>
        {onRetry && (
          <>
            <div className="alert-actions"><button type="button" className="secondary small" onClick={onRetry}><RotateCcw aria-hidden="true" />Try again</button></div>
            <p className="small m-0 mt-2">If this keeps happening, use <strong>Report a problem</strong> on a lesson or contact your instructor or administrator.</p>
          </>
        )}
      </div>
    </div>
  )
}

const TONE: Record<string, string> = {
  approved: 'ok', active: 'ok', ok: 'ok', attained: 'ok', mastered: 'ok', ready: 'ok', done: 'ok', enrolled: 'ok', resolved: 'ok', upheld: 'ok', verified: 'ok', completed: 'ok', given: 'ok', published: 'ok',
  pending: 'warn', in_review: 'warn', under_review: 'warn', preview: 'warn', developing: 'warn', in_progress: 'warn', suggested: 'warn', open: 'warn', submitted: 'warn', fallback: 'warn', acknowledged: 'warn', locked: 'warn',
  rejected: 'bad', not_ready: 'bad', error: 'bad', withdrawn: 'bad', blocked: 'bad', retired: 'bad', below: 'bad', superseded: '',
  draft: '', not_started: '',
}
/** DESIGN.md §5 status labels (display text only — the stored status value is unchanged). */
const LABEL: Record<string, string> = {
  attained: 'Mastered', below: 'Needs review', pending: 'Pending review', in_review: 'Pending review',
  not_started: 'Not started', in_progress: 'In progress', draft: 'Draft',
}
const ICON_BY_STATUS: Record<string, LucideIcon> = {
  draft: Pencil, not_started: Circle, pending: Clock, in_review: Clock, under_review: Clock, in_progress: Clock, submitted: Clock, developing: Clock,
  rejected: XCircle, withdrawn: XCircle, retired: XCircle, blocked: XCircle,
  below: AlertCircle, not_ready: AlertCircle, error: AlertCircle,
}
const ICON_BY_TONE: Record<string, LucideIcon> = { ok: CheckCircle2, warn: Clock, bad: AlertCircle, info: Info }

const sentence = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s)

/** Status badge: colour + icon + text label (never colour alone). Non-status values render as a plain neutral chip. */
export function Badge({ value, tone }: { value: string | number | boolean | null | undefined; tone?: string }) {
  const raw = String(value ?? '—')
  const t = tone ?? TONE[raw] ?? ''
  const Icon = ICON_BY_STATUS[raw] ?? (t ? ICON_BY_TONE[t] : undefined)
  return <span className={`badge ${t}`}>{Icon && <Icon aria-hidden="true" />}{LABEL[raw] ?? sentence(raw.replace(/_/g, ' '))}</span>
}

/**
 * Progress / mastery bar (DESIGN.md §5): 8px, percentage written next to it, and the mastery
 * threshold drawn as a labelled marker. `label` names it for screen readers.
 */
export function Bar({ value, threshold, label = 'Progress', showValue = true }: { value: number; threshold?: number; label?: string; showValue?: boolean }) {
  const v = Math.max(0, Math.min(100, value))
  const tone = threshold === undefined ? '' : v >= threshold ? 'ok' : 'bad'
  const text = `${Math.round(v)}%${threshold === undefined ? '' : ` (target ${threshold}%)`}`
  const edge = threshold === undefined ? '' : threshold > 85 ? ' at-end' : threshold < 15 ? ' at-start' : ''
  return (
    <div className={`bar-wrap${threshold === undefined ? '' : ' has-target'}`}>
      <div className="bar-track">
        <div className={`bar ${tone}`} role="progressbar" aria-label={label} aria-valuetext={text} aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${v}%` }} />
        </div>
        {threshold !== undefined && (
          <>
            <span className="bar-marker" style={{ left: `${threshold}%` }} aria-hidden="true" />
            <span className={`bar-target${edge}`} style={{ left: `${threshold}%` }} aria-hidden="true">Target {threshold}%</span>
          </>
        )}
      </div>
      {showValue && <span className="bar-value" aria-hidden="true">{Math.round(v)}%</span>}
    </div>
  )
}

/** Load data from an async function; re-run with reload(). */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps)
  const reload = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await run())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [run])
  useEffect(() => {
    reload()
  }, [reload])
  return { data, error, loading, reload, setData }
}

/** Wrap an action so its error/success message can be shown. Success messages also appear as a toast. */
export function useAction() {
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function run<T>(fn: () => Promise<T>, success?: string): Promise<T | undefined> {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const r = await fn()
      if (success) { setMessage(success); toast(success) }
      return r
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return { error, message, busy, run, setError, setMessage }
}

/** Loading state (DESIGN.md §7): skeleton shaped like the content, with an accessible label. */
export function Loading({ variant = 'lines', label = 'Loading…' }: { variant?: 'lines' | 'cards' | 'table' | 'spinner'; label?: string }) {
  if (variant === 'spinner') return <span className="spinner" role="status">{label}</span>
  return (
    <div role="status" aria-live="polite" className="mb-4">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true">
        {variant === 'cards' ? (
          <div className="skeleton-grid"><span className="skeleton block" /><span className="skeleton block" /><span className="skeleton block" /></div>
        ) : variant === 'table' ? (
          <div className="table-wrap"><span className="skeleton skeleton-row" /><span className="skeleton skeleton-row" /><span className="skeleton skeleton-row" /><span className="skeleton skeleton-row" /></div>
        ) : (
          <div className="skeleton-group"><span className="skeleton line title" /><span className="skeleton line" /><span className="skeleton line" /><span className="skeleton line short" /></div>
        )}
      </div>
    </div>
  )
}

/** Empty state (DESIGN.md §7): icon, one-line title, one sentence, one action. */
export function EmptyState({ icon: Icon = Info, title, children, action }: { icon?: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <Icon className="icon" aria-hidden="true" />
      <p className="empty-title">{title}</p>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

/** Breadcrumbs for deep pages (DESIGN.md §5 Navigation). The last item is the current page. */
export function Crumbs({ items }: { items: { to?: string; label: string }[] }) {
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((it, i) => (
          <li key={i}>{it.to && i < items.length - 1 ? <Link to={it.to}>{it.label}</Link> : <span aria-current={i === items.length - 1 ? 'page' : undefined}>{it.label}</span>}</li>
        ))}
      </ol>
    </nav>
  )
}

export function fmtDate(s?: string | null) {
  if (!s) return '—'
  // One clear format everywhere, with the viewer's time zone (e.g. "10 Nov 2026, 14:05 GMT+5").
  return new Date(s.endsWith('Z') ? s : s + 'Z').toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  })
}
