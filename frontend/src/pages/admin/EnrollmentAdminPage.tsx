import { useState } from 'react'
import { api } from '../../api/client'
import { Alert, Badge, fmtDate, useAction, useLoad } from '../../components/ui'

type U = { id: number; full_name: string; student_number: string | null }
type Sec = { id: number; code: string; course: { code: string; title: string; status: string }; term: { name: string }; enrolled: number; capacity: number }
type Enr = { id: number; status: string; course: { code: string }; term: string; section: { code: string }; enrolled_at: string; withdraw_reason: string | null; prerequisite_override: boolean; override_reason: string | null }

export default function EnrollmentAdminPage() {
  const students = useLoad(() => api<U[]>('/users?role=student'))
  const sections = useLoad(() => api<Sec[]>('/offerings/sections'))
  const [sid, setSid] = useState('')
  const [sec, setSec] = useState('')
  const [override, setOverride] = useState(false)
  const [reason, setReason] = useState('')
  const hist = useLoad(() => (sid ? api<Enr[]>(`/enrollment/student/${sid}`) : Promise.resolve([] as Enr[])), [sid])
  const act = useAction()

  async function enrol() {
    const body = { student_id: Number(sid), section_id: Number(sec), override_prerequisites: override, reason }
    if (await act.run(() => api('/enrollment/admin', { body }), 'Enrolled')) {
      hist.reload()
      sections.reload()
    }
  }

  return (
    <>
      <h1>Enrolment administration</h1>
      <p className="muted">Enrol a student on their behalf (optionally overriding prerequisites with a recorded reason), mark completions, and see the full history including withdrawals.</p>
      <div className="card">
        <div className="grid">
          <div className="field"><label htmlFor="es">Student</label>
            <select id="es" value={sid} onChange={(e) => setSid(e.target.value)}><option value="">Choose…</option>{students.data?.map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.student_number})</option>)}</select></div>
          <div className="field"><label htmlFor="ese">Section</label>
            <select id="ese" value={sec} onChange={(e) => setSec(e.target.value)}><option value="">Choose…</option>{sections.data?.filter((s) => s.course.status === 'active').map((s) => <option key={s.id} value={s.id}>{s.course.code} {s.term.name} {s.code} ({s.enrolled}/{s.capacity})</option>)}</select></div>
          <div className="field">
            <label className="inline-check"><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} /> Override prerequisites and the semester roadmap</label>
            {override && <label className="inline-field"><span className="inline-field-label">Override reason</span><input placeholder="Reason (e.g. transfer credit)" value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
          </div>
        </div>
        <button disabled={!sid || !sec} onClick={enrol}>Enrol student</button>
        <Alert>{act.error}</Alert>
      </div>
      {sid && (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)"><table>
          <thead><tr><th>Course</th><th>Section</th><th>Status</th><th>Since</th><th>Notes</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>{hist.data?.map((e) => (
            <tr key={e.id}>
              <td>{e.course.code}</td><td>{e.term} {e.section.code}</td><td><Badge value={e.status} /></td><td className="small">{fmtDate(e.enrolled_at)}</td>
              <td className="small">{e.withdraw_reason}{e.prerequisite_override && `Prerequisite override: ${e.override_reason}`}</td>
              <td>{e.status === 'enrolled' && <button className="secondary" onClick={async () => { if (await act.run(() => api(`/enrollment/${e.id}/complete`, { method: 'POST' }), 'Marked completed')) hist.reload() }}>Mark completed</button>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </>
  )
}
