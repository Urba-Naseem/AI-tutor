/**
 * Component kit - "The marked notebook" (Ui design brief §4). Built once, reused by every screen.
 * Styles: styles/kit.css (tokens only). Status words: ./status.ts.
 */
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Loader2, MoreHorizontal, X } from 'lucide-react'
import { type ButtonHTMLAttributes, type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { band, BAND_TONE, statusText, statusTone, type Tone } from './status'

/* ── 1. Button ─────────────────────────────────────────────────────────────────────────────────────────── */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md'; loading?: boolean; icon?: ReactNode }
export function Button({ variant = 'primary', size = 'md', loading, icon, children, className = '', disabled, ...rest }: ButtonProps) {
  return (
    <button type="button" {...rest} disabled={disabled || loading} aria-busy={loading || undefined}
      className={`kbtn kbtn-${variant} kbtn-${size} ${className}`.trim()}>
      {loading ? <Loader2 className="kbtn-spin" aria-hidden="true" /> : icon}
      <span>{children}</span>
    </button>
  )
}

/* ── 2. Card ───────────────────────────────────────────────────────────────────────────────────────────── */
export function Card({ title, subtitle, action, footer, ruled, children, className = '', titleId }: { title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; footer?: ReactNode; ruled?: boolean; children?: ReactNode; className?: string; titleId?: string }) {
  const auto = useId()
  const id = titleId ?? `card-${auto}`
  return (
    <section className={`kcard${ruled ? ' kcard-ruled' : ''} ${className}`.trim()} aria-labelledby={title ? id : undefined}>
      {(title || action) && (
        <header className="kcard-head">
          <div className="min-w-0">
            {title && <h2 id={id} className="kcard-title">{title}</h2>}
            {subtitle && <p className="kcard-sub">{subtitle}</p>}
          </div>
          {action && <div className="kcard-action">{action}</div>}
        </header>
      )}
      <div className="kcard-body">{children}</div>
      {footer && <footer className="kcard-foot">{footer}</footer>}
    </section>
  )
}

/* ── 4. MasteryBar (signature): fill to the score, red tick at the threshold, label above the tick ──────── */
export function MasteryBar({ value, threshold = 60, attained, size = 'md', label, showTarget = true }: { value: number | null | undefined; threshold?: number; attained?: boolean | null; size?: 'sm' | 'md' | 'lg'; label?: string; showTarget?: boolean }) {
  const b = band(value, threshold, attained)
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, value))
  const words = b === 'insufficient' ? 'not enough evidence yet' : statusText(b).toLowerCase()
  const name = `${label ? `${label}: ` : ''}${value === null || value === undefined ? 'no score' : `${Math.round(pct)}%`}, threshold ${threshold}%, ${words}`
  return (
    <div className={`mbar mbar-${size} mbar-${BAND_TONE[b]}`} role="img" aria-label={name}>
      {showTarget && size !== 'sm' && <span className="mbar-target" style={{ left: `${threshold}%` }} aria-hidden="true">{threshold}%</span>}
      <span className="mbar-track" aria-hidden="true">
        <span className="mbar-fill" style={{ width: `${pct}%` }} />
        <span className="mbar-tick" style={{ left: `${threshold}%` }} />
      </span>
    </div>
  )
}

/* Mastery ring: circular score with the red threshold tick (path map nodes, outcomes). */
export function ScoreRing({ value, threshold = 60, attained, size = 36, label }: { value: number | null | undefined; threshold?: number; attained?: boolean | null; size?: number; label?: string }) {
  const b = band(value, threshold, attained)
  const stroke = Math.max(3, Math.round(size / 9))
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const v = value ?? 0
  const a = (threshold / 100) * 2 * Math.PI - Math.PI / 2
  const [x1, y1, x2, y2] = [size / 2 + (r - stroke) * Math.cos(a), size / 2 + (r - stroke) * Math.sin(a), size / 2 + (r + stroke) * Math.cos(a), size / 2 + (r + stroke) * Math.sin(a)]
  return (
    <span className={`sring sring-${BAND_TONE[b]}`} role="img" aria-label={`${label ? `${label}: ` : ''}${value == null ? 'no score yet' : `${Math.round(v)}%`}, target ${threshold}%`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="sring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        {value != null && <circle className="sring-fill" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(100, v) / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />}
        <line className="sring-tick" x1={x1} y1={y1} x2={x2} y2={y2} strokeWidth={Math.max(2, stroke / 2)} strokeLinecap="round" />
      </svg>
      {size >= 32 && <span className="sring-value" aria-hidden="true">{value == null ? '–' : Math.round(v)}</span>}
    </span>
  )
}

/* Overall progress ring: steps completed / total, number in the middle. */
export function ProgressRing({ done, total, size = 112, caption = 'steps' }: { done: number; total: number; size?: number; caption?: string }) {
  const stroke = 10
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const share = total ? done / total : 0
  return (
    <span className="pring" role="img" aria-label={`${done} of ${total} ${caption} completed`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="pring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        {done > 0 && <circle className="pring-fill" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - share)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />}
      </svg>
      <span className="pring-center" aria-hidden="true"><strong>{done}</strong><span>/ {total} {caption}</span></span>
    </span>
  )
}

/* ── 6. Status pill: dot + text, colour from the status (never colour alone) ─────────────────────────── */
export function StatusPill({ status, tone, children }: { status?: string | null; tone?: Tone; children?: ReactNode }) {
  const t = tone ?? statusTone(status)
  return <span className={`pill pill-${t}`}><span className="pill-dot" aria-hidden="true" />{children ?? statusText(status)}</span>
}

/* ── 3. Stat tile: label, big number, context line, optional mini mastery bar ─────────────────────────── */
export function StatTile({ label, value, suffix, context, contextTone, bar }: { label: string; value: ReactNode; suffix?: ReactNode; context?: ReactNode; contextTone?: Tone; bar?: { value: number | null; threshold: number; attained?: boolean | null } }) {
  return (
    <div className="ktile">
      <p className="ktile-label">{label}</p>
      <p className="ktile-value">{value}{suffix && <span className="ktile-suffix"> {suffix}</span>}</p>
      {bar && <MasteryBar value={bar.value} threshold={bar.threshold} attained={bar.attained} size="sm" label={label} />}
      {context && <p className={`ktile-context${contextTone ? ` tone-${contextTone}` : ''}`}>{context}</p>}
    </div>
  )
}

/* ── 5. OutcomeRow: CLO code · description · MasteryBar · score + status pill ────────────────────────── */
export function OutcomeRow({ code, description, value, threshold = 60, attained, note, compact }: { code: string; description: string; value: number | null | undefined; threshold?: number; attained?: boolean | null; note?: ReactNode; compact?: boolean }) {
  const b = band(value, threshold, attained)
  return (
    <div className={`orow${compact ? ' orow-compact' : ''}`}>
      <strong className="orow-code">{code}</strong>
      <span className="orow-desc">{description}</span>
      <span className="orow-score tabular" aria-hidden="true">{value == null ? '—' : `${Math.round(value)}%`}</span>
      <div className="orow-bar"><MasteryBar value={value} threshold={threshold} attained={attained} size={compact ? 'sm' : 'md'} label={code} showTarget={false} /></div>
      <span className="orow-pill"><StatusPill status={b} /></span>
      {note && <span className="orow-note">{note}</span>}
    </div>
  )
}

/* ── 8. Form field: label, help, error under the field (linked with aria-describedby), required marker ── */
export function Field({ label, help, error, required, children }: { label: string; help?: ReactNode; error?: ReactNode; required?: boolean; children: (a: { id: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean; required?: boolean }) => ReactNode }) {
  const id = useId()
  const describedBy = [help ? `${id}-help` : '', error ? `${id}-err` : ''].filter(Boolean).join(' ') || undefined
  return (
    <div className="kfield">
      <label htmlFor={id} className="kfield-label">{label}{required && <span className="kfield-req"> (required)</span>}</label>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined, required })}
      {help && <p id={`${id}-help`} className="kfield-help">{help}</p>}
      {error && <p id={`${id}-err`} className="kfield-error" role="alert">{error}</p>}
    </div>
  )
}

/* ── 9a. Segmented switch (e.g. Map / List) ──────────────────────────────────────────────────────────── */
export function Segmented<T extends string>({ label, options, value, onChange, chips }: { label: string; options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; chips?: boolean }) {
  return (
    <div className={`kseg${chips ? ' kchips' : ''}`} role="group" aria-label={label}>
      {options.map((o) => <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  )
}

/* ── 9b. Tabs (arrow keys move between tabs) ─────────────────────────────────────────────────────────── */
export function Tabs({ label, tabs }: { label: string; tabs: { id: string; label: string; content: ReactNode }[] }) {
  const [active, setActive] = useState(tabs[0]?.id)
  const base = useId()
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const move = (i: number) => { const t = tabs[(i + tabs.length) % tabs.length]; setActive(t.id); refs.current[(i + tabs.length) % tabs.length]?.focus() }
  return (
    <div className="ktabs">
      <div role="tablist" aria-label={label} className="ktabs-list">
        {tabs.map((t, i) => (
          <button key={t.id} ref={(el) => { refs.current[i] = el }} role="tab" type="button" id={`${base}-${t.id}`} aria-selected={active === t.id} aria-controls={`${base}-${t.id}-panel`}
            tabIndex={active === t.id ? 0 : -1} onClick={() => setActive(t.id)}
            onKeyDown={(e) => { if (e.key === 'ArrowRight') move(i + 1); if (e.key === 'ArrowLeft') move(i - 1); if (e.key === 'Home') move(0); if (e.key === 'End') move(tabs.length - 1) }}>{t.label}</button>
        ))}
      </div>
      {tabs.map((t) => (
        <div key={t.id} role="tabpanel" id={`${base}-${t.id}-panel`} aria-labelledby={`${base}-${t.id}`} hidden={active !== t.id} tabIndex={0} className="ktabs-panel">{t.content}</div>
      ))}
    </div>
  )
}

/* ── 9c. Modal and Drawer: focus trapped, Esc closes, focus returns to the opener ─────────────────────── */
function useDialogFocus(open: boolean, onClose: () => void) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    const focusables = () => [...(box.current?.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])') ?? [])]
    requestAnimationFrame(() => (focusables()[0] ?? box.current)?.focus())
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose() }
      if (e.key !== 'Tab') return
      const f = focusables()
      if (!f.length) return
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus() }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); opener?.focus() }
  }, [open, onClose])
  return box
}

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const box = useDialogFocus(open, onClose)
  const id = useId()
  if (!open) return null
  return (
    <div className="kscrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={box} className={`kmodal${wide ? ' kmodal-wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1}>
        <header className="kmodal-head"><h2 id={id}>{title}</h2><button type="button" className="kicon-btn" onClick={onClose} aria-label="Close"><X aria-hidden="true" /></button></header>
        <div className="kmodal-body">{children}</div>
        {footer && <footer className="kmodal-foot">{footer}</footer>}
      </div>
    </div>
  )
}

export function Drawer({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }) {
  const box = useDialogFocus(open, onClose)
  const id = useId()
  if (!open) return null
  return (
    <div className="kscrim kscrim-drawer" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div ref={box} className="kdrawer" role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1}>
        <header className="kmodal-head"><h2 id={id}>{title}</h2><button type="button" className="kicon-btn" onClick={onClose} aria-label="Close"><X aria-hidden="true" /></button></header>
        <div className="kmodal-body">{children}</div>
        {footer && <footer className="kmodal-foot">{footer}</footer>}
      </div>
    </div>
  )
}

/* ── 7. Table: sticky header, sortable columns, row hover, empty state, row actions in a menu ─────────── */
export type Column<T> = { key: string; header: string; sort?: (r: T) => string | number; align?: 'left' | 'right'; render: (r: T) => ReactNode }
export function DataTable<T>({ caption, columns, rows, rowKey, empty, actions }: { caption: string; columns: Column<T>[]; rows: T[]; rowKey: (r: T) => string | number; empty?: ReactNode; actions?: (r: T) => { label: string; onSelect: () => void; danger?: boolean }[] }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null)
  const col = columns.find((c) => c.key === sort?.key)
  const shown = col?.sort ? [...rows].sort((a, b) => { const x = col.sort!(a), y = col.sort!(b); return (x < y ? -1 : x > y ? 1 : 0) * sort!.dir }) : rows
  if (!rows.length) return <div className="ktable-empty">{empty ?? 'Nothing here yet.'}</div>
  return (
    <div className="ktable-wrap" tabIndex={0} role="region" aria-label={`${caption} (scroll sideways if it does not fit)`}>
      <table className="ktable">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => {
              const dir = sort?.key === c.key ? sort.dir : 0
              return (
                <th key={c.key} scope="col" className={c.align === 'right' ? 'num' : undefined} aria-sort={dir === 1 ? 'ascending' : dir === -1 ? 'descending' : c.sort ? 'none' : undefined}>
                  {c.sort ? (
                    <button type="button" className="ktable-sort" onClick={() => setSort({ key: c.key, dir: dir === 1 ? -1 : 1 })}>
                      {c.header}{dir === 1 ? <ArrowUp aria-hidden="true" /> : dir === -1 ? <ArrowDown aria-hidden="true" /> : <ArrowUpDown aria-hidden="true" />}
                    </button>
                  ) : c.header}
                </th>
              )
            })}
            {actions && <th scope="col" className="num"><span className="sr-only">Actions</span></th>}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => <td key={c.key} className={c.align === 'right' ? 'num' : undefined}>{c.render(r)}</td>)}
              {actions && <td className="num"><RowMenu items={actions(r)} /></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RowMenu({ items }: { items: { label: string; onSelect: () => void; danger?: boolean }[] }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => { if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close); document.addEventListener('keydown', close)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close) }
  }, [open])
  return (
    <div className="krowmenu" ref={box}>
      <button type="button" className="kicon-btn" aria-label="Row actions" aria-expanded={open} onClick={() => setOpen(!open)}><MoreHorizontal aria-hidden="true" /></button>
      {open && <ul className="krowmenu-list">{items.map((i) => <li key={i.label}><button type="button" className={i.danger ? 'is-danger' : ''} onClick={() => { setOpen(false); i.onSelect() }}>{i.label}</button></li>)}</ul>}
    </div>
  )
}

/* ── 12. Stepper / path list: done = green check, current = action outline + tinted row, upcoming = grey ─ */
export function Stepper({ steps }: { steps: { id: string | number; title: ReactNode; meta?: ReactNode; reason?: ReactNode; status: 'done' | 'current' | 'upcoming'; action?: ReactNode }[] }) {
  return (
    <ol className="kstep">
      {steps.map((s, i) => (
        <li key={s.id} className={`kstep-item is-${s.status}`} aria-current={s.status === 'current' ? 'step' : undefined}>
          <span className="kstep-dot" aria-hidden="true">{s.status === 'done' ? <Check /> : i + 1}</span>
          <div className="kstep-body">
            <div className="kstep-title">{s.title}{s.meta && <span className="kstep-meta">{s.meta}</span>}</div>
            {s.reason && <p className="kstep-reason">{s.reason}</p>}
          </div>
          {s.action && <div className="kstep-action">{s.action}</div>}
          <span className="sr-only">{s.status === 'done' ? 'Done' : s.status === 'current' ? 'Current step' : 'Coming up'}</span>
        </li>
      ))}
    </ol>
  )
}

/* Vertical timeline (path changes, version history): ring marker coloured by the event's tone. */
export function Timeline({ events }: { events: { id: string | number; tone: Tone; title: ReactNode; detail?: ReactNode; when: ReactNode }[] }) {
  return (
    <ol className="ktl">
      {events.map((e) => (
        <li key={e.id} className={`ktl-item tone-${e.tone}`}>
          <span className="ktl-dot" aria-hidden="true" />
          <div className="ktl-body"><p className="ktl-title">{e.title}</p>{e.detail && <p className="ktl-detail">{e.detail}</p>}</div>
          <span className="ktl-when">{e.when}</span>
        </li>
      ))}
    </ol>
  )
}

/* ── 11. Skeleton shaped like the content ────────────────────────────────────────────────────────────── */
export function Skeleton({ lines = 3, label = 'Loading…' }: { lines?: number; label?: string }) {
  return (
    <div className="kskel" role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, i) => <span key={i} className="kskel-line" style={{ width: `${92 - i * 14}%` }} />)}
    </div>
  )
}
