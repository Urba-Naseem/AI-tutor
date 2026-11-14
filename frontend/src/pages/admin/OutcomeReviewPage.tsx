import { CheckCircle2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { askConfirm } from '../../components/dialogApi'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Badge, EmptyState, Loading, useAction, useLoad } from '../../components/ui'

type Issue = { key: string; level: string; path: string; message: string; acknowledged: boolean; ack_note: string | null }
type CourseT = { id: number; code: string; title: string; credits: number | null; semester: number | null; prerequisites: string[]; status: string; units: { id: number; number: number; title: string }[]; clos: { id: number; code: string; description: string; unit_id: number | null; weight?: number | null }[] }
type Review = {
  version: { id: number; program_key: string; version_no: number; status: string }
  program: { id: number; code: string; name: string }
  plos: { id: number; code: string; description: string }[]
  courses: CourseT[]
  issues: Issue[]
  can_approve: boolean
}

/** Text that saves itself when it loses focus. */
function Edit({ value, onSave, label, multiline, disabled, width, describedBy, invalid }: { value: string; onSave: (v: string) => void; label: string; multiline?: boolean; disabled?: boolean; width?: number; describedBy?: string; invalid?: boolean }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  const props = { 'aria-label': label, 'aria-describedby': describedBy, 'aria-invalid': invalid || undefined, value: v, disabled, onChange: (e: { target: { value: string } }) => setV(e.target.value), onBlur: () => v !== value && onSave(v), style: width ? { width } : undefined }
  return multiline ? <textarea {...props} className="textarea-compact" /> : <input {...props} />
}

export default function OutcomeReviewPage() {
  const { vid } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const versions = useLoad(() => api<{ id: number; program_key: string; version_no: number; status: string }[]>('/outcomes/in-review'))
  const { data, error, loading, reload } = useLoad(() => (vid ? api<Review>(`/outcomes/versions/${vid}`) : Promise.resolve(null)), [vid])
  const act = useAction()
  const [ackNote, setAckNote] = useState<Record<string, string>>({})
  const isAdmin = user?.role === 'admin'

  async function call(path: string, method: string, body?: object) {
    await act.run(() => api(path, { method, body }))
    reload()
  }

  if (!vid)
    return (
      <>
        <h1>Outcome review</h1>
        <p className="muted">Pick a curriculum version. Start a review from the Curriculum upload page.</p>
        {versions.loading ? <Loading variant="table" /> : versions.data?.length ? (
          <ul>{versions.data.map((v) => <li key={v.id}><a href={`/outcomes/review/${v.id}`} onClick={(e) => { e.preventDefault(); nav(`/outcomes/review/${v.id}`) }}>{v.program_key} v{v.version_no}</a> <Badge value={v.status} /></li>)}</ul>
        ) : <EmptyState icon={CheckCircle2} title="No versions in review">Upload a curriculum to start a new review.</EmptyState>}
      </>
    )
  if (loading && !data) return <Loading />
  if (!data) return <Alert>{error}</Alert>
  const editable = data.version.status === 'in_review'
  const errors = data.issues.filter((i) => i.level === 'error')
  const warnings = data.issues.filter((i) => i.level === 'warning')
  // course codes used by more than one course (errors at "course:CODE/duplicate"): shown again next to each code box
  const dupCodes = new Set(errors.filter((i) => i.path.endsWith('/duplicate')).map((i) => i.path.slice('course:'.length, -'/duplicate'.length)))
  const openWarnings = warnings.filter((w) => !w.acknowledged).length

  return (
    <>
      <div className="spread">
        <h1>Review {data.version.program_key} v{data.version.version_no} <Badge value={data.version.status} /></h1>
        {editable && isAdmin && (
          <div className="approve-box">
            <button disabled={!data.can_approve || act.busy} aria-describedby={data.can_approve ? undefined : 'approve-why'} onClick={() => call(`/outcomes/versions/${vid}/approve`, 'POST')}>Approve outcomes</button>
            {!data.can_approve && (errors.length > 0 || openWarnings > 0) && (
              <p id="approve-why" className="field-hint m-0">
                To approve: {errors.length > 0 && <>fix the {errors.length} error{errors.length > 1 ? 's' : ''} below</>}{errors.length > 0 && openWarnings > 0 && ' and '}{openWarnings > 0 && <>accept or fix {openWarnings} warning{openWarnings > 1 ? 's' : ''}</>}.
              </p>
            )}
          </div>
        )}
      </div>
      <Alert>{act.error}</Alert>
      {error && <Alert onRetry={reload}>{error}</Alert>}
      {data.version.status === 'approved' && <Alert kind="success">Approved — this structure is now the curriculum source of truth and is locked. With automation on, linking CLOs to PLOs, activating the courses and drafting their questions now continue in the background.</Alert>}

      <div className="card">
        <h2 className="mt-0">Issues: {errors.length} errors, {warnings.filter((w) => !w.acknowledged).length} open warnings</h2>
        <p className="small muted">Errors must be corrected. Warnings must be fixed or accepted with a reason. Approval is blocked until then. Notes marked "Info" need no action.</p>
        {editable && warnings.some((w) => !w.acknowledged) && (
          <div className="row mb-2">
            <label className="inline-field"><span className="inline-field-label">Reason for accepting all warnings</span><input placeholder="Reason for accepting all open warnings" className="max-w-sm" value={ackNote['*'] ?? ''} onChange={(e) => setAckNote({ ...ackNote, '*': e.target.value })} /></label>
            <button className="secondary" disabled={(ackNote['*'] ?? '').trim().length < 5} onClick={() => call(`/outcomes/versions/${vid}/ack-all`, 'POST', { note: ackNote['*'] })}>Accept all warnings</button>
          </div>
        )}
        <ul className="stack list-indent">
          {data.issues.map((i) => (
            <li key={i.key}>
              <Badge value={i.acknowledged ? 'accepted' : i.level} tone={i.acknowledged ? 'ok' : i.level === 'error' ? 'bad' : i.level === 'info' ? 'info' : 'warn'} /> {i.message}
              {i.acknowledged && <span className="small muted"> — {i.ack_note}</span>}
              {editable && i.level === 'warning' && !i.acknowledged && (
                <span className="row mt-1">
                  <label className="inline-field"><span className="inline-field-label">Reason for accepting</span><input placeholder="Reason for accepting as-is" className="max-w-sm" value={ackNote[i.key] ?? ''} onChange={(e) => setAckNote({ ...ackNote, [i.key]: e.target.value })} /></label>
                  <button className="secondary" onClick={() => call(`/outcomes/versions/${vid}/ack`, 'POST', { issue_key: i.key, note: ackNote[i.key] ?? '' })}>Accept</button>
                </span>
              )}
            </li>
          ))}
          {!data.issues.length && <li>No issues — ready to approve.</li>}
        </ul>
      </div>

      <div className="card">
        <h2 className="mt-0">Programme</h2>
        <div className="row">
          <Edit label="Programme code" value={data.program.code} disabled={!editable || !isAdmin} width={140} onSave={(v) => call(`/outcomes/programs/${data.program.id}`, 'PATCH', { code: v })} />
          <div className="flex-1"><Edit label="Programme name" value={data.program.name} disabled={!editable || !isAdmin} onSave={(v) => call(`/outcomes/programs/${data.program.id}`, 'PATCH', { name: v })} /></div>
        </div>
        <h3>PLOs</h3>
        {data.plos.map((p) => (
          <div className="row mb-2" key={p.id}>
            <Edit label={`${p.code} code`} value={p.code} width={90} disabled={!editable || !isAdmin} onSave={(v) => call(`/outcomes/plos/${p.id}`, 'PATCH', { code: v })} />
            <div className="flex-1"><Edit label={`${p.code} description`} value={p.description} disabled={!editable || !isAdmin} onSave={(v) => call(`/outcomes/plos/${p.id}`, 'PATCH', { description: v })} /></div>
            {editable && isAdmin && <button className="secondary" aria-label={`Delete ${p.code}`} onClick={() => call(`/outcomes/plos/${p.id}`, 'DELETE')}>✕</button>}
          </div>
        ))}
        {editable && isAdmin && <button className="secondary" onClick={() => call(`/outcomes/programs/${data.program.id}/plos`, 'POST', { code: `PLO${data.plos.length + 1}`, description: '' })}>+ Add PLO</button>}
      </div>

      {data.courses.map((c) => (
        <div className="card" key={c.id}>
          <div className="row">
            <Edit label={`Course code of ${c.title}`} value={c.code} width={110} disabled={!editable} invalid={dupCodes.has(c.code)} describedBy={dupCodes.has(c.code) ? `dup-${c.id}` : undefined} onSave={(v) => call(`/outcomes/courses/${c.id}`, 'PATCH', { code: v })} />
            <div className="flex-1"><Edit label="Course title" value={c.title} disabled={!editable} onSave={(v) => call(`/outcomes/courses/${c.id}`, 'PATCH', { title: v })} /></div>
            <label className="inline-field"><span className="inline-field-label">Credits</span><Edit label="Credits" value={String(c.credits ?? '')} width={70} disabled={!editable} onSave={(v) => call(`/outcomes/courses/${c.id}`, 'PATCH', { credits: Number(v) || null })} /></label>
            <label className="inline-field"><span className="inline-field-label">Semester</span><Edit label={`Roadmap semester of ${c.code} (blank = not limited)`} value={String(c.semester ?? '')} width={70} disabled={!editable} onSave={(v) => call(`/outcomes/courses/${c.id}`, 'PATCH', { semester: Number(v) || null })} /></label>
            <Badge value={c.status} />
            {editable && isAdmin && <button className="danger" onClick={async () => {
              if (await askConfirm({ title: `Delete ${c.code}?`, message: `${c.code} and its outcomes will be removed from this draft version. This cannot be undone.`, confirmLabel: `Delete ${c.code}`, danger: true }))
                call(`/outcomes/courses/${c.id}`, 'DELETE')
            }}>Delete</button>}
          </div>
          {dupCodes.has(c.code) && (
            <p id={`dup-${c.id}`} className="field-error">Another course also uses the code {c.code}. Type this course's own code in the code box above, then click outside the box to save.</p>
          )}
          <div className="row small mt-2">
            <span>Prerequisites (comma-separated):</span>
            <Edit label="Prerequisites" value={c.prerequisites.join(', ')} width={240} disabled={!editable} onSave={(v) => call(`/outcomes/courses/${c.id}`, 'PATCH', { prerequisites: v.split(',').map((x) => x.trim()).filter(Boolean) })} />
          </div>
          {c.units.map((u) => (
            <div key={u.id} className="unit-block">
              <div className="row">
                <strong>Unit {u.number}</strong>
                <div className="flex-1"><Edit label={`Unit ${u.number} title`} value={u.title} disabled={!editable} onSave={(v) => call(`/outcomes/units/${u.id}`, 'PATCH', { title: v })} /></div>
                {editable && <button className="secondary" aria-label={`Delete unit ${u.number}`} onClick={() => call(`/outcomes/units/${u.id}`, 'DELETE')}>✕</button>}
              </div>
              {c.clos.filter((o) => o.unit_id === u.id).map((o) => <CloRow key={o.id} o={o} units={c.units} editable={editable} call={call} />)}
            </div>
          ))}
          {c.clos.filter((o) => !o.unit_id).length > 0 && (
            <div className="mt-3">
              <Badge value="CLOs without a unit" tone="bad" />
              {c.clos.filter((o) => !o.unit_id).map((o) => <CloRow key={o.id} o={o} units={c.units} editable={editable} call={call} />)}
            </div>
          )}
          {editable && (
            <div className="row mt-2">
              <button className="secondary" onClick={() => call(`/outcomes/courses/${c.id}/units`, 'POST', { title: 'New unit' })}>+ Unit</button>
              <button className="secondary" onClick={() => call(`/outcomes/courses/${c.id}/clos`, 'POST', { description: '', unit_id: c.units[0]?.id ?? null })}>+ CLO</button>
            </div>
          )}
        </div>
      ))}
      {editable && isAdmin && <button className="secondary" onClick={() => call(`/outcomes/versions/${vid}/courses`, 'POST', { code: 'NEW101', title: 'New course' })}>+ Add missing course</button>}
    </>
  )
}

function CloRow({ o, units, editable, call }: { o: CourseT['clos'][0]; units: CourseT['units']; editable: boolean; call: (p: string, m: string, b?: object) => void }) {
  return (
    <div className="row mt-2">
      <Edit label={`${o.code} code`} value={o.code} width={80} disabled={!editable} onSave={(v) => call(`/outcomes/clos/${o.id}`, 'PATCH', { code: v })} />
      <div className="flex-1 min-w-lg"><Edit label={`${o.code} description`} value={o.description} multiline disabled={!editable} onSave={(v) => call(`/outcomes/clos/${o.id}`, 'PATCH', { description: v })} /></div>
      <label className="inline-field"><span className="inline-field-label">Weight %</span>
        <Edit label={`${o.code} weight in percent`} value={o.weight == null ? '' : String(o.weight)} width={72} disabled={!editable}
          onSave={(v) => { const n = v.trim() === '' ? null : Number(v); if (n === null || (Number.isFinite(n) && n >= 0 && n <= 100)) call(`/outcomes/clos/${o.id}`, 'PATCH', { weight: n }) }} />
      </label>
      <select aria-label={`${o.code} unit`} className="w-sm" disabled={!editable} value={o.unit_id ?? ''} onChange={(e) => call(`/outcomes/clos/${o.id}`, 'PATCH', { unit_id: Number(e.target.value) })}>
        <option value="" disabled>Unit…</option>
        {units.map((u) => <option key={u.id} value={u.id}>Unit {u.number}</option>)}
      </select>
      {editable && <button className="secondary" aria-label={`Delete ${o.code}`} onClick={() => call(`/outcomes/clos/${o.id}`, 'DELETE')}>✕</button>}
    </div>
  )
}
