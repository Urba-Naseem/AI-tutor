import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import ConsentPanel from '../components/ConsentPanel'
import PasswordInput from '../components/PasswordInput'
import { Alert, useAction } from '../components/ui'
import { StaffProfile } from './StaffProfile'

export default function AccountPage() {
  const { user } = useAuth()
  const [cur, setCur] = useState('')
  const [pw, setPw] = useState('')
  const act = useAction()
  async function submit(e: FormEvent) {
    e.preventDefault()
    await act.run(() => api('/auth/change-password', { body: { current_password: cur, new_password: pw } }), 'Password changed')
    setCur('')
    setPw('')
  }
  return (
    <>
      <h1>My account</h1>
      <div className="card">
        <p><strong>{user?.full_name}</strong> — {user?.email}</p>
        <p className="muted">Role: {user?.role}{user?.student_number ? ` · Student no. ${user.student_number}` : ''}{user?.program_code ? ` · Department: ${user.program_code}` : ''}</p>
      </div>
      {user?.role === 'student' && <ConsentPanel />}
      {(user?.role === 'instructor' || user?.role === 'admin') && <StaffProfile />}
      <form className="card max-w-md" onSubmit={submit}>
        <h2>Change password</h2>
        <div className="field"><label htmlFor="cur">Current password</label><PasswordInput id="cur" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required /></div>
        <div className="field">
          <label htmlFor="new">New password</label>
          <PasswordInput id="new" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required aria-describedby="new-hint" />
          <p id="new-hint" className="field-hint">At least 10 characters, with letters and digits.</p>
        </div>
        <Alert>{act.error}</Alert>
        <button disabled={act.busy}>Change password</button>
      </form>
    </>
  )
}
