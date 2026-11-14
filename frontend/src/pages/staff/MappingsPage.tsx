import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { Alert, Badge, Loading, useAction, useLoad } from '../../components/ui'
import { useCourses } from './SourcesPage'

type Cov = {
  course: { id: number; code: string; title: string; status: string }
  clos: { id: number; code: string; description: string }[]
  plos: { id: number; code: string; description: string }[]
  mappings: { id: number; clo_id: number; plo_id: number; strength: number; origin: string; status: string; rationale: string | null }[]
  unmapped_clos: string[]; uncovered_plos: string[]; pending_suggestions: number; complete: boolean; can_activate: boolean; blockers: string[]
}

export default function MappingsPage() {
  const [params, setParams] = useSearchParams()
  const courseId = params.get('course') ?? ''
  const courses = useCourses()
  const cov = useLoad(() => (courseId ? api<Cov>(`/mappings/course/${courseId}`) : Promise.resolve(null)), [courseId])
  const act = useAction()
  const [sel, setSel] = useState<{ clo: string; plo: string; strength: string }>({ clo: '', plo: '', strength: '2' })
  const set = (d: Cov | undefined) => d && cov.setData(d)
  const d = cov.data
  const locked = d?.course.status !== 'approved'

  return (
    <>
      <h1>CLO–PLO mappings &amp; activation</h1>
      <p className="muted">Every CLO needs at least one approved PLO mapping before the course can be activated. Suggestions from the curriculum document or AI must be approved by a person.</p>
      <div className="field max-w-md">
        <label htmlFor="mc">Course</label>
        <select id="mc" value={courseId} onChange={(e) => setParams({ course: e.target.value })}>
          <option value="">Choose…</option>
          {courses.data?.filter((c) => ['approved', 'active'].includes(c.status)).map((c) => <option key={c.id} value={c.id}>{c.code} {c.title} ({c.status})</option>)}
        </select>
      </div>
      <Alert>{act.error}</Alert>
      {cov.error && <Alert onRetry={cov.reload}>{cov.error}</Alert>}
      {cov.loading && courseId ? <Loading variant="table" /> : d && (
        <>
          <div className="card">
            <div className="spread">
              <div><strong>{d.course.code}</strong> {d.course.title} <Badge value={d.course.status} /></div>
              {!locked && (
                <div className="row">
                  <button className="secondary" onClick={async () => set(await act.run(() => api<Cov>(`/mappings/course/${courseId}/import-document`, { method: 'POST' }), 'Imported mappings stated in the curriculum'))}>Import from document</button>
                  <button className="secondary" onClick={async () => set(await act.run(() => api<Cov>(`/mappings/course/${courseId}/suggest`, { method: 'POST' }), 'AI suggestions added for review'))}>Suggest with AI</button>
                  <button disabled={!d.can_activate} onClick={async () => { set(await act.run(() => api<Cov>(`/courses/${courseId}/activate`, { method: 'POST' }), 'Course activated. Next: in Offerings & faculty, create a section and assign an instructor so they can build the item bank and content, and students can enrol.')); courses.reload() }}>Activate course</button>
                </div>
              )}
            </div>
            {d.blockers.length > 0 && <Alert kind="error">Activation blocked: {d.blockers.join('; ')}</Alert>}
            {d.uncovered_plos.length > 0 && <p className="small muted">PLOs not addressed by this course (fine for one course, shown for programme roll-up): {d.uncovered_plos.join(', ')}</p>}
          </div>

          <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
            <table>
              <thead><tr><th>CLO</th>{d.plos.map((p) => <th key={p.id} title={p.description}>{p.code}</th>)}</tr></thead>
              <tbody>
                {d.clos.map((o) => (
                  <tr key={o.id}>
                    <td className="max-w-sm"><strong>{o.code}</strong> {d.unmapped_clos.includes(o.code) && <Badge value="unmapped" tone="bad" />}<div className="small muted">{o.description}</div></td>
                    {d.plos.map((p) => {
                      const m = d.mappings.find((x) => x.clo_id === o.id && x.plo_id === p.id && x.status !== 'rejected')
                      return (
                        <td key={p.id} className="text-center">
                          {m ? (
                            <div title={m.rationale ?? ''}>
                              <Badge value={m.status === "approved" ? `Approved · strength ${m.strength}` : `Suggested (${m.origin}) · strength ${m.strength}`} tone={m.status === "approved" ? "ok" : "warn"} />
                              {m.status === 'suggested' && !locked && (
                                <div className="row justify-center mt-1">
                                  <button className="small" aria-label={`Approve ${o.code} to ${p.code}`} title="Approve" onClick={async () => set(await act.run(() => api<Cov>(`/mappings/${m.id}/decide`, { body: { decision: 'approve' } })))}><Check aria-hidden="true" /></button>
                                  <button className="small danger" aria-label={`Reject ${o.code} to ${p.code}`} title="Reject" onClick={async () => set(await act.run(() => api<Cov>(`/mappings/${m.id}/decide`, { body: { decision: 'reject' } })))}><X aria-hidden="true" /></button>
                                </div>
                              )}
                            </div>
                          ) : <span className="muted">·</span>}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!locked && (
            <div className="card row mt-3">
              <strong>Add mapping</strong>
              <label className="inline-field"><span className="inline-field-label">CLO</span><select className="w-sm" value={sel.clo} onChange={(e) => setSel({ ...sel, clo: e.target.value })}><option value="">CLO…</option>{d.clos.map((o) => <option key={o.id} value={o.id}>{o.code}</option>)}</select></label>
              <label className="inline-field"><span className="inline-field-label">PLO</span><select className="w-sm" value={sel.plo} onChange={(e) => setSel({ ...sel, plo: e.target.value })}><option value="">PLO…</option>{d.plos.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</select></label>
              <label className="inline-field"><span className="inline-field-label">Strength</span><select className="w-sm" value={sel.strength} onChange={(e) => setSel({ ...sel, strength: e.target.value })}><option value="1">1 low</option><option value="2">2 medium</option><option value="3">3 high</option></select></label>
              <button disabled={!sel.clo || !sel.plo} onClick={async () => set(await act.run(() => api<Cov>('/mappings', { body: { clo_id: Number(sel.clo), plo_id: Number(sel.plo), strength: Number(sel.strength) } }), 'Mapping approved'))}>Add &amp; approve</button>
            </div>
          )}
        </>
      )}
    </>
  )
}
