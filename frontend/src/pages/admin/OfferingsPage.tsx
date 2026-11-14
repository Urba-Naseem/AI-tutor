import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import { Segmented } from '../../components/kit/Kit'
import { Alert, Badge, Loading, useAction, useLoad } from '../../components/ui'

type Term = { id: number; name: string; start_date: string; end_date: string }
type Asg = { id: number; instructor_id: number; instructor_name: string; role: string; start_date: string; end_date: string | null; end_reason: string | null; active: boolean }
type Sec = { id: number; code: string; capacity: number; enrolled: number; status: string; course: { id: number; code: string; title: string; status: string; program?: string | null }; term: Term; instructors: Asg[]; history: Asg[]; needs_instructor: boolean }
type Course = { id: number; code: string; title: string; status: string; prerequisites: string[]; program?: string | null; semester?: number | null }
type U = { id: number; full_name: string; is_active: boolean }

export default function OfferingsPage() {
  const terms = useLoad(() => api<Term[]>('/offerings/terms'))
  const sections = useLoad(() => api<Sec[]>('/offerings/sections'))
  const courses = useLoad(() => api<Course[]>('/outcomes/courses'))
  const instructors = useLoad(() => api<U[]>('/users?role=instructor'))
  const act = useAction()
  const [term, setTerm] = useState({ name: '', start_date: '', end_date: '' })
  const [sec, setSec] = useState({ course_id: '', term_id: '', code: 'A', capacity: '40' })
  const [bulk, setBulk] = useState({ program_code: '', semester: '1', term_id: '', code: 'A', capacity: '40' })
  const [hand, setHand] = useState<Record<number, { to: string; reason: string }>>({})
  const [prereq, setPrereq] = useState<Record<number, { codes: string; reason: string }>>({})
  const [history, setHistory] = useState<number | null>(null)

  // department switch: every list on this page follows it (remembered for next time)
  const [dept, setDept] = useState<string>(() => { try { return localStorage.getItem('offeringsDept') ?? '' } catch { return '' } })
  const pickDept = (d: string) => { setDept(d); try { localStorage.setItem('offeringsDept', d) } catch { /* storage unavailable */ } }
  const depts = [...new Set((courses.data ?? []).map((c) => c.program).filter((p): p is string => !!p))].sort()
  const inDept = (p?: string | null) => !dept || p === dept
  const offerable = (courses.data ?? []).filter((c) => ['approved', 'active'].includes(c.status) && inDept(c.program))
  const shownSections = (sections.data ?? []).filter((s) => inDept(s.course.program))
  const activeInstr = (instructors.data ?? []).filter((u) => u.is_active)
  const reloadAll = () => { sections.reload(); courses.reload() }

  async function addTerm(e: FormEvent) {
    e.preventDefault()
    if (await act.run(() => api('/offerings/terms', { body: term }), 'Term created')) terms.reload()
  }
  async function addSection(e: FormEvent) {
    e.preventDefault()
    if (await act.run(() => api('/offerings/sections', { body: { course_id: Number(sec.course_id), term_id: Number(sec.term_id), code: sec.code, capacity: Number(sec.capacity) } }), 'Section created')) sections.reload()
  }
  async function post(path: string, body: object, msg: string) {
    if (await act.run(() => api(path, { body }), msg)) reloadAll()
  }

  return (
    <>
      <h1>Offerings &amp; faculty</h1>
      <p className="muted">Offer approved courses in terms and sections, set capacity, assign instructors and hand a section over if an instructor leaves mid-semester (history is kept and reviews follow the new instructor).</p>
      {depts.length > 1 && (
        <div className="row mb-2"><Segmented chips label="Department" options={[{ value: '', label: 'All departments' }, ...depts.map((d) => ({ value: d, label: d }))]} value={dept} onChange={pickDept} /></div>
      )}
      <Alert>{act.error}</Alert>
      {sections.error && <Alert onRetry={sections.reload}>{sections.error}</Alert>}

      <div className="grid grid-wide">
        <form className="card" onSubmit={addTerm}>
          <h2 className="mt-0">New term</h2>
          <div className="field"><label htmlFor="tn">Name</label><input id="tn" required value={term.name} onChange={(e) => setTerm({ ...term, name: e.target.value })} placeholder="Fall 2026" /></div>
          <div className="row">
            <div className="field flex-1"><label htmlFor="ts">Starts</label><input id="ts" type="date" required value={term.start_date} onChange={(e) => setTerm({ ...term, start_date: e.target.value })} /></div>
            <div className="field flex-1"><label htmlFor="te">Ends</label><input id="te" type="date" required value={term.end_date} onChange={(e) => setTerm({ ...term, end_date: e.target.value })} /></div>
          </div>
          <button>Create term</button>
          <p className="small muted">{terms.data?.map((t) => t.name).join(' · ')}</p>
        </form>
        <form className="card" onSubmit={addSection}>
          <h2 className="mt-0">New section</h2>
          <div className="field"><label htmlFor="sc">Course</label>
            <select id="sc" required value={sec.course_id} onChange={(e) => setSec({ ...sec, course_id: e.target.value })}>
              <option value="">Choose…</option>
              {(dept ? [dept] : depts.length ? depts : ['']).map((d) => (
                <optgroup key={d || 'all'} label={d ? `${d} department` : 'Courses'}>
                  {offerable.filter((c) => !d || c.program === d).map((c) => <option key={c.id} value={c.id}>{c.code} {c.title} ({c.status})</option>)}
                </optgroup>
              ))}
            </select></div>
          <div className="field"><label htmlFor="st">Term</label>
            <select id="st" required value={sec.term_id} onChange={(e) => setSec({ ...sec, term_id: e.target.value })}>
              <option value="">Choose…</option>{terms.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select></div>
          <div className="row">
            <div className="field flex-1"><label htmlFor="scode">Section code</label><input id="scode" value={sec.code} onChange={(e) => setSec({ ...sec, code: e.target.value })} /></div>
            <div className="field flex-1"><label htmlFor="scap">Capacity</label><input id="scap" type="number" min={1} value={sec.capacity} onChange={(e) => setSec({ ...sec, capacity: e.target.value })} /></div>
          </div>
          <button>Create section</button>
        </form>
        <form className="card" onSubmit={async (e) => {
          e.preventDefault()
          const prog = dept || bulk.program_code
          const r = await act.run(() => api<{ created: unknown[]; skipped: string[] }>('/offerings/sections/semester', { body: { program_code: prog, semester: Number(bulk.semester), term_id: Number(bulk.term_id), code: bulk.code, capacity: Number(bulk.capacity) } }))
          if (r) { act.setMessage(`${r.created.length} section${r.created.length === 1 ? '' : 's'} created${r.skipped.length ? ` · already there: ${r.skipped.join(', ')}` : ''}`); reloadAll() }
        }}>
          <h2 className="mt-0">Sections for a whole semester</h2>
          <p className="small muted">One section for every course of a department's semester (from its roadmap). Assign instructors afterwards in the table below.</p>
          {!dept && (
            <div className="field"><label htmlFor="bp">Department</label>
              <select id="bp" required value={bulk.program_code} onChange={(e) => setBulk({ ...bulk, program_code: e.target.value })}>
                <option value="">Choose…</option>{depts.map((d) => <option key={d} value={d}>{d}</option>)}
              </select></div>
          )}
          <div className="row">
            <div className="field flex-1"><label htmlFor="bs">Semester</label>
              <select id="bs" value={bulk.semester} onChange={(e) => setBulk({ ...bulk, semester: e.target.value })}>
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => {
                  const k = (courses.data ?? []).filter((c) => c.semester === n && ['approved', 'active'].includes(c.status) && c.program === (dept || bulk.program_code)).length
                  return <option key={n} value={n}>Semester {n}{(dept || bulk.program_code) ? ` (${k} course${k === 1 ? '' : 's'})` : ''}</option>
                })}
              </select></div>
            <div className="field flex-1"><label htmlFor="bt">Term</label>
              <select id="bt" required value={bulk.term_id} onChange={(e) => setBulk({ ...bulk, term_id: e.target.value })}>
                <option value="">Choose…</option>{terms.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select></div>
          </div>
          <div className="row">
            <div className="field flex-1"><label htmlFor="bcode">Section code</label><input id="bcode" value={bulk.code} onChange={(e) => setBulk({ ...bulk, code: e.target.value })} /></div>
            <div className="field flex-1"><label htmlFor="bcap">Capacity</label><input id="bcap" type="number" min={1} value={bulk.capacity} onChange={(e) => setBulk({ ...bulk, capacity: e.target.value })} /></div>
          </div>
          <button disabled={act.busy}>Create semester sections</button>
          {act.message && <Alert kind="success">{act.message}</Alert>}
        </form>
      </div>

      {(() => {
        const offered = new Set(shownSections.filter((s) => !s.needs_instructor).map((s) => s.course.id))
        const missing = offerable.filter((c) => !offered.has(c.id))
        if (!missing.length) return null
        return (
          <Alert kind="info">
            These courses have no section with an instructor yet, so no instructor can see them (item bank, content, console)
            and students cannot enrol: {missing.map((c) => `${c.code}${!dept && c.program ? ` [${c.program}]` : ''} (${c.status})`).join(', ')}. Create a section above and assign an instructor.
          </Alert>
        )
      })()}
      <h2>Sections</h2>
      {sections.loading ? <Loading variant="table" /> : (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
          <table>
            <thead><tr><th>Course</th><th>Department</th><th>Term / section</th><th>Seats</th><th>Instructor(s)</th><th>Assign / hand over</th></tr></thead>
            <tbody>
              {shownSections.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.course.code}</strong> {s.course.title}<div><Badge value={s.course.status} /></div></td>
                  <td>{s.course.program ?? '—'}</td>
                  <td>{s.term.name} · {s.code}<div><Badge value={s.status} /></div></td>
                  <td>{s.enrolled}/{s.capacity}</td>
                  <td>
                    {s.instructors.map((i) => <div key={i.id}>{i.instructor_name} <span className="small muted">({i.role} since {i.start_date})</span></div>)}
                    {s.needs_instructor && <Badge value="needs instructor" tone="bad" />}
                    <div><button className="secondary small" onClick={() => setHistory(history === s.id ? null : s.id)}>History ({s.history.length})</button></div>
                    {history === s.id && (
                      <ul className="small">{s.history.map((h) => <li key={h.id}>{h.instructor_name} ({h.role}) {h.start_date} → {h.end_date ?? 'now'}{h.end_reason && ` — ${h.end_reason}`}</li>)}</ul>
                    )}
                  </td>
                  <td className="min-w-lg">
                    <select aria-label="Instructor" value={hand[s.id]?.to ?? ''} onChange={(e) => setHand({ ...hand, [s.id]: { ...hand[s.id], to: e.target.value } })}>
                      <option value="">Instructor…</option>{activeInstr.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                    </select>
                    {s.needs_instructor ? (
                      <button className="secondary small mt-2" disabled={!hand[s.id]?.to} onClick={() => post(`/offerings/sections/${s.id}/assign`, { instructor_id: Number(hand[s.id].to) }, 'Instructor assigned')}>Assign</button>
                    ) : (
                      <>
                        <label className="inline-field mt-2"><span className="inline-field-label">Reason for hand-over</span><input placeholder="Reason (e.g. resigned)" value={hand[s.id]?.reason ?? ''} onChange={(e) => setHand({ ...hand, [s.id]: { ...hand[s.id], reason: e.target.value } })} /></label>
                        <div className="row mt-2">
                          <button className="secondary small" disabled={!hand[s.id]?.to} onClick={() => post(`/offerings/sections/${s.id}/reassign`, { new_instructor_id: Number(hand[s.id].to), reason: hand[s.id]?.reason ?? '' }, 'Section handed over')}>Hand over</button>
                          <button className="secondary" disabled={!hand[s.id]?.to} onClick={() => post(`/offerings/sections/${s.id}/assign`, { instructor_id: Number(hand[s.id].to), role: 'assistant' }, 'Assistant added')}>Add assistant</button>
                        </div>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Prerequisites</h2>
      <p className="small muted">Changes after approval require a reason and are checked for unknown codes and circular chains.</p>
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
        <table>
          <thead><tr><th>Course</th><th>Department</th><th>Current</th><th>Change</th></tr></thead>
          <tbody>
            {offerable.map((c) => (
              <tr key={c.id}>
                <td><strong>{c.code}</strong> {c.title}</td>
                <td>{c.program ?? '—'}</td>
                <td>{c.prerequisites.join(', ') || 'none'}</td>
                <td className="row">
                  <input aria-label={`Prerequisites for ${c.code}`} className="max-w-xs" placeholder="CS101, MATH110" value={prereq[c.id]?.codes ?? c.prerequisites.join(', ')} onChange={(e) => setPrereq({ ...prereq, [c.id]: { ...prereq[c.id], codes: e.target.value } })} />
                  <label className="inline-field"><span className="inline-field-label">Reason</span><input className="max-w-xs" placeholder="Reason" value={prereq[c.id]?.reason ?? ''} onChange={(e) => setPrereq({ ...prereq, [c.id]: { ...prereq[c.id], reason: e.target.value } })} /></label>
                  <button className="secondary" onClick={async () => {
                    const p = prereq[c.id] ?? { codes: c.prerequisites.join(','), reason: '' }
                    if (await act.run(() => api(`/offerings/courses/${c.id}/prerequisites`, { method: 'PUT', body: { prerequisites: (p.codes ?? '').split(',').map((x) => x.trim()).filter(Boolean), reason: p.reason ?? '' } }), 'Prerequisites updated')) courses.reload()
                  }}>Save</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
