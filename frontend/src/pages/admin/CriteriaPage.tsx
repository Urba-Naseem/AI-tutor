import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import { askText } from '../../components/dialogApi'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Badge, fmtDate, Loading, useAction, useLoad } from '../../components/ui'

type Crit = { id: number; scope_type: string; scope_key: string; version_no: number; threshold: number | null; reason: string; created_by_name: string | null; effective_from: string; superseded_at: string | null; current: boolean }
type Course = { id: number; code: string; title: string; status: string }
type CourseDetail = { id: number; program_id: number; clos: { id: number; code: string; description: string }[] }
type Eff = { clo_id: number; clo_code: string; threshold: number; scope_key: string; version_no: number }

export default function CriteriaPage() {
  const { user } = useAuth()
  const canEdit = user?.role === 'admin'
  const crit = useLoad(() => api<{ current: Crit[]; history: Crit[] }>('/criteria'))
  const courses = useLoad(() => api<Course[]>('/outcomes/courses'))
  const [courseId, setCourseId] = useState<number | null>(null)
  const detail = useLoad(() => (courseId ? api<CourseDetail>(`/outcomes/courses/${courseId}`) : Promise.resolve(null)), [courseId])
  const eff = useLoad(() => (courseId ? api<{ clos: Eff[] }>(`/criteria/effective/course/${courseId}`) : Promise.resolve(null)), [courseId])
  const act = useAction()
  const [form, setForm] = useState({ scope_type: 'course', ref: '', threshold: '70', reason: '' })

  const usable = (courses.data ?? []).filter((c) => c.status !== 'superseded')
  const refresh = () => { crit.reload(); eff.reload() }

  async function submit(e: FormEvent) {
    e.preventDefault()
    let ref_id: number | null = null
    if (form.scope_type === 'program') ref_id = detail.data?.program_id ?? null
    else if (form.scope_type === 'course') ref_id = courseId
    else if (form.scope_type === 'clo') ref_id = Number(form.ref)
    if (await act.run(() => api('/criteria', { body: { scope_type: form.scope_type, ref_id, threshold: Number(form.threshold), reason: form.reason } }), 'Criterion saved as a new version')) {
      setForm({ ...form, reason: '' })
      refresh()
    }
  }

  return (
    <>
      <h1>Attainment criteria</h1>
      <p className="muted">A CLO is attained when mastery reaches the threshold. The institutional default is 60%. Overrides can be set per programme, course or CLO — the most specific one wins. Every change creates a new version, so past decisions can be reproduced.</p>
      <Alert>{act.error}</Alert>
      {crit.error && <Alert onRetry={crit.reload}>{crit.error}</Alert>}

      <div className="card">
        <div className="field max-w-md">
          <label htmlFor="cc">Course</label>
          <select id="cc" value={courseId ?? ''} onChange={(e) => setCourseId(Number(e.target.value) || null)}>
            <option value="">Choose a course…</option>
            {usable.map((c) => <option key={c.id} value={c.id}>{c.code} {c.title} ({c.status})</option>)}
          </select>
        </div>
        {courseId && (eff.loading ? <Loading variant="table" /> : (
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
            <table>
              <thead><tr><th>CLO</th><th>Threshold</th><th>Comes from</th></tr></thead>
              <tbody>{eff.data?.clos.map((c) => (
                <tr key={c.clo_id}><td>{c.clo_code}</td><td><strong>{c.threshold}%</strong></td><td><code>{c.scope_key}</code> v{c.version_no}</td></tr>
              ))}</tbody>
            </table>
          </div>
        ))}
      </div>

      {canEdit && (
        <form className="card" onSubmit={submit}>
          <h2 className="mt-0">Set a threshold</h2>
          <div className="grid">
            <div className="field"><label htmlFor="st">Scope</label>
              <select id="st" value={form.scope_type} onChange={(e) => setForm({ ...form, scope_type: e.target.value })}>
                <option value="global">Institution (default)</option>
                <option value="program" disabled={!courseId}>Programme of selected course</option>
                <option value="course" disabled={!courseId}>Selected course</option>
                <option value="clo" disabled={!courseId}>A CLO of selected course</option>
              </select></div>
            {form.scope_type === 'clo' && (
              <div className="field"><label htmlFor="sclo">CLO</label>
                <select id="sclo" required value={form.ref} onChange={(e) => setForm({ ...form, ref: e.target.value })}>
                  <option value="">Choose…</option>{detail.data?.clos.map((o) => <option key={o.id} value={o.id}>{o.code}</option>)}
                </select></div>
            )}
            <div className="field"><label htmlFor="th">Threshold %</label><input id="th" type="number" min={1} max={100} value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} /></div>
            <div className="field"><label htmlFor="rs">Reason</label><input id="rs" required value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Board of Studies decision" /></div>
          </div>
          <button disabled={act.busy}>Save new version</button>
        </form>
      )}

      <h2>Current overrides</h2>
      {crit.loading ? <Loading variant="table" /> : (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
          <table>
            <thead><tr><th>Scope</th><th>Threshold</th><th>Version</th><th>Reason</th><th>Since</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>{crit.data?.current.map((c) => (
              <tr key={c.id}>
                <td><code>{c.scope_key}</code></td><td><strong>{c.threshold}%</strong></td><td>v{c.version_no}</td><td>{c.reason}</td><td className="small">{fmtDate(c.effective_from)}</td>
                <td>{canEdit && c.scope_type !== 'global' && courseId && (
                  <button className="secondary" onClick={async () => {
                    const reason = await askText({
                      title: `Remove the ${c.scope_key} override?`,
                      message: `The ${c.threshold}% threshold will stop applying and the inherited attainment criterion will be used again. The change is recorded in the audit log.`,
                      inputLabel: 'Reason for removing this override',
                      confirmLabel: 'Remove override',
                      danger: true,
                    })
                    if (!reason) return
                    const ref = c.scope_type === 'program' ? detail.data?.program_id : c.scope_type === 'course' ? courseId : detail.data?.clos.find((o) => c.scope_key.endsWith('/' + o.code))?.id
                    if (ref && (await act.run(() => api(`/criteria/remove/${c.scope_type}/${ref}`, { body: { reason } }), 'Override removed'))) refresh()
                  }}>Remove</button>
                )}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      <h2>Version history</h2>
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
        <table>
          <thead><tr><th>Scope</th><th>Version</th><th>Threshold</th><th>Reason</th><th>By</th><th>In force</th></tr></thead>
          <tbody>{crit.data?.history.map((c) => (
            <tr key={c.id}>
              <td><code>{c.scope_key}</code></td><td>v{c.version_no}</td><td>{c.threshold === null ? <Badge value="removed" /> : `${c.threshold}%`}</td><td>{c.reason}</td><td>{c.created_by_name ?? 'system'}</td>
              <td className="small">{fmtDate(c.effective_from)} → {c.superseded_at ? fmtDate(c.superseded_at) : <Badge value="current" tone="ok" />}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  )
}
