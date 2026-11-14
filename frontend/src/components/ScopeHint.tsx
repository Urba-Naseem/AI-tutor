import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

/** Explains course scope (US-11.1): instructors only see courses they are assigned to teach. */
export default function ScopeHint({ count }: { count?: number }) {
  const { user } = useAuth()
  if (user?.role === 'admin') return null
  return (
    <p className="small muted mt-1">
      {count === 0 ? <strong>You are not assigned to teach any approved or active course yet. </strong> : null}
      Only courses you currently teach are listed. If a course is missing, an administrator must assign you to one of its
      sections in <em>Offerings &amp; faculty</em>.
    </p>
  )
}

/** For admins: reminder that a course needs a section and an instructor before teachers can work on it. */
export function AssignHint() {
  const { user } = useAuth()
  if (user?.role !== 'admin') return null
  return (
    <p className="small muted mt-1">
      Instructors only see a course once they are assigned to one of its sections in{' '}
      <Link to="/admin/offerings">Offerings &amp; faculty</Link>.
    </p>
  )
}
