import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import { askText } from '../../components/dialogApi'
import { Alert, Badge, fmtDate, Loading, useAction, useLoad } from '../../components/ui'

type U = { id: number; email: string; full_name: string; role: string; is_active: boolean; locked: boolean; last_login_at: string | null; student_number: string | null; program_code: string | null }
const ROLES = ['student', 'instructor', 'admin', 'exam_staff']

export default function UsersPage() {
  const { data, error, loading, reload } = useLoad(() => api<U[]>('/users'))
  const act = useAction()
  const progs = useLoad(() => api<{ code: string; name: string }[]>('/users/programs'))
  const [form, setForm] = useState({ email: '', full_name: '', role: 'instructor', password: '', student_number: '', program_code: '' })
  const [filter, setFilter] = useState('')
  const [dept, setDept] = useState('')
  const deptName = (c: string | null) => progs.data?.find((p) => p.code === c)?.name ?? c ?? '—'

  async function create(e: FormEvent) {
    e.preventDefault()
    const r = await act.run(() => api('/users', { body: { ...form, student_number: form.student_number || null, program_code: form.role === 'student' ? form.program_code || null : null } }), 'User created')
    if (r) {
      setForm({ ...form, email: '', full_name: '', password: '', student_number: '' })
      reload()
    }
  }
  async function moveDept(u: U, code: string) {
    if (!code || code === u.program_code) return
    let reason: string | null = null
    if (u.program_code) {
      reason = await askText({ title: `Move ${u.full_name} to ${deptName(code)}?`, message: 'The student will only see and enrol in courses of the new department. Their history is kept.', inputLabel: 'Reason for the move', confirmLabel: 'Move student' })
      if (!reason) return
    }
    await patch(u.id, { program_code: code, reason })
  }
  async function patch(id: number, body: object) {
    await act.run(() => api(`/users/${id}`, { method: 'PATCH', body }), 'Saved')
    reload()
  }

  return (
    <>
      <h1>Users &amp; roles</h1>
      <p className="muted">Roles are enforced on the server: students, instructors, administrators and exam staff only reach the actions and courses within their scope.</p>
      <form className="card" onSubmit={create}>
        <h2>Create account</h2>
        <div className="grid">
          <div className="field"><label htmlFor="nu-name">Full name</label><input id="nu-name" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
          <div className="field"><label htmlFor="nu-email">E-mail</label><input id="nu-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div className="field"><label htmlFor="nu-role">Role</label><select id="nu-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></div>
          <div className="field"><label htmlFor="nu-pw">Initial password</label><input id="nu-pw" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          {form.role === 'student' && <div className="field"><label htmlFor="nu-sn">Student number</label><input id="nu-sn" value={form.student_number} onChange={(e) => setForm({ ...form, student_number: e.target.value })} /></div>}
          {form.role === 'student' && (progs.data?.length ?? 0) > 0 && (
            <div className="field"><label htmlFor="nu-dept">Department</label>
              <select id="nu-dept" required value={form.program_code} onChange={(e) => setForm({ ...form, program_code: e.target.value })}>
                <option value="">Choose…</option>{progs.data!.map((p) => <option key={p.code} value={p.code}>{p.name} ({p.code})</option>)}
              </select></div>
          )}
        </div>
        <button disabled={act.busy}>Create</button>
      </form>
      <Alert>{act.error}</Alert>
      {error && <Alert onRetry={reload}>{error}</Alert>}
      <div className="row mb-2">
        <label htmlFor="filter" className="m-0">Filter by role</label>
        <select id="filter" className="w-md" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All</option>{ROLES.map((r) => <option key={r}>{r}</option>)}
        </select>
        {(progs.data?.length ?? 0) > 0 && (
          <>
            <label htmlFor="dept-filter" className="m-0">Department</label>
            <select id="dept-filter" className="w-md" value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">All</option>{progs.data!.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}<option value="none">Students without a department</option>
            </select>
          </>
        )}
      </div>
      {loading ? <Loading variant="table" /> : (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
          <table>
            <thead><tr><th>Name</th><th>E-mail</th><th>Role</th><th>Department</th><th>Status</th><th>Last login</th><th>Actions</th></tr></thead>
            <tbody>
              {data?.filter((u) => (!filter || u.role === filter) && (!dept || (dept === 'none' ? u.role === 'student' && !u.program_code : u.program_code === dept))).map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}{u.student_number && <div className="small muted">{u.student_number}</div>}</td>
                  <td>{u.email}</td>
                  <td>
                    <select aria-label={`Role for ${u.full_name}`} value={u.role} onChange={(e) => patch(u.id, { role: e.target.value })}>
                      {ROLES.map((r) => <option key={r}>{r}</option>)}
                    </select>
                  </td>
                  <td>{u.role === 'student' && (progs.data?.length ?? 0) > 0 ? (
                    <select aria-label={`Department for ${u.full_name}`} value={u.program_code ?? ''} onChange={(e) => moveDept(u, e.target.value)}>
                      {!u.program_code && <option value="">Not set</option>}
                      {progs.data!.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
                    </select>
                  ) : <span className="muted">—</span>}</td>
                  <td><Badge value={u.is_active ? 'active' : 'disabled'} tone={u.is_active ? 'ok' : 'bad'} /> {u.locked && <Badge value="locked" />}</td>
                  <td className="small">{fmtDate(u.last_login_at)}</td>
                  <td className="row">
                    <button className="secondary" onClick={() => patch(u.id, { is_active: !u.is_active })}>{u.is_active ? 'Disable' : 'Enable'}</button>
                    {u.locked && <button className="secondary" onClick={() => act.run(() => api(`/users/${u.id}/unlock`, { method: 'POST' })).then(reload)}>Unlock</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
