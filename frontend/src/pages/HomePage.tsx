import { ArrowRight, BarChart3, BookPlus, CheckCircle2, ChevronRight, ClipboardCheck, Compass, Route, Sparkles } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth, type Role } from '../auth/AuthContext'
import { PathChart, Ring } from '../components/charts'
import { NAV_DESC, NAV_ICON } from '../components/navIcons'
import { Alert, EmptyState, Loading, useLoad } from '../components/ui'
import { routes } from '../routes'
import { PrerequisitePathCard, type Status } from './student/DiagnosticPage'
import { PathSteps, STEP_LINKS, type Path } from './student/PathPage'
import { CloMasteryList, type Progress } from './student/ProgressPage'

type Course = { id: number; code: string; title: string }

// The student Home is the course page from the mockup (charts load on demand)
const StudentCourseHome = lazy(() => import('./student/CoursePage').then((m) => ({ default: m.StudentCourseHome })))

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

/** No path yet: take the diagnostic, or (semester 2+ with a completed prerequisite) build it from that result. */
function NoPathStep({ courseId, onBuilt }: { courseId: string; onBuilt: () => void }) {
  const st = useLoad(() => api<Status>(`/diagnostic/${courseId}/status`), [courseId])
  if (st.loading && !st.data) return <Loading variant="cards" label="Loading your next step…" />
  if (st.data?.needed === false) return <PrerequisitePathCard courseId={courseId} reason={st.data.reason} onBuilt={onBuilt} />
  return (
    <section className="card next-step" aria-labelledby="next-title">
      <p className="eyebrow"><Sparkles className="icon-inline" aria-hidden="true" /> Your next step</p>
      <h2 id="next-title" className="mt-0"><ClipboardCheck className="icon" aria-hidden="true" />Take the diagnostic test</h2>
      <p className="card-desc">A short, untimed test finds what you already know and builds your personal learning path.</p>
      <div className="card-actions"><Link className="btn" to={`/learn/${courseId}/diagnostic`}>Start diagnostic<ArrowRight aria-hidden="true" /></Link></div>
    </section>
  )
}

/** "Your next step" card (DESIGN.md §6 student dashboard): one primary button. */
function NextStep({ path, courseId, onBuilt }: { path: Path | null; courseId: string; onBuilt: () => void }) {
  if (!path) return <NoPathStep courseId={courseId} onBuilt={onBuilt} />
  const next = path.steps.find((s) => s.id === path.next_step_id)
  if (!next) {
    return (
      <section className="card next-step" aria-labelledby="next-title">
        <p className="eyebrow"><Sparkles className="icon-inline" aria-hidden="true" /> Your next step</p>
        <h2 id="next-title" className="mt-0"><CheckCircle2 className="icon text-success" aria-hidden="true" /> Learning path complete</h2>
        <p className="card-desc">You have finished every step. Review your progress or keep practising any outcome.</p>
        <div className="card-actions"><Link className="btn" to={`/learn/${courseId}/progress`}>Review my progress</Link></div>
      </section>
    )
  }
  const link = STEP_LINKS[next.step_type]?.(courseId, next)
  return (
    <section className="card next-step" aria-labelledby="next-title">
      <p className="eyebrow"><Sparkles className="icon-inline" aria-hidden="true" /> Your next step · Unit {next.unit_number}</p>
      <h2 id="next-title" className="mt-0">{next.label} <span className="chip">{next.clo_code}</span></h2>
      <p className="m-0">{next.clo_description}</p>
      <p className="why"><strong>Why this step:</strong> {next.rationale}</p>
      <div className="card-actions">{link ? <Link className="btn" to={link}>Start this step<ArrowRight aria-hidden="true" /></Link> : <Link className="btn" to={`/learn/${courseId}/path`}>Open my learning path</Link>}</div>
    </section>
  )
}

/** Right-hand summary next to the next step: path progress ring + outcomes mastered + weak areas. */
function ProgressCard({ path, prog, courseId }: { path: Path | null; prog: Progress | null; courseId: string }) {
  const pct = path ? (100 * path.progress.done) / Math.max(1, path.progress.total) : 0
  return (
    <section className="card" aria-labelledby="glance-title">
      <h2 id="glance-title" className="mt-0 card-title">At a glance</h2>
      <div className="glance">
        <Ring value={pct} label="Learning path progress" caption={path ? `${path.progress.done} of ${path.progress.total} steps` : 'no path yet'} done={!!path && path.progress.done === path.progress.total} />
        {prog ? (
          <dl className="glance-facts">
            <div><dt>Outcomes mastered</dt><dd>{prog.summary.attained} / {prog.summary.total}</dd></div>
            <div><dt>Weak areas</dt><dd>{prog.weak_areas.length}</dd></div>
          </dl>
        ) : <p className="muted small m-0">Progress appears after your first activity.</p>}
        <Link className="small" to={`/learn/${courseId}/progress`}>Full progress report</Link>
      </div>
    </section>
  )
}

function CourseDashboard({ course }: { course: Course }) {
  const id = String(course.id)
  const path = useLoad(() => api<Path | null>(`/paths/me/${id}`), [id])
  const prog = useLoad(() => api<Progress>(`/progress/me/${id}`), [id])
  return (
    <>
      {path.loading && !path.data ? <Loading variant="cards" label="Loading your next step…" /> : path.error ? <Alert onRetry={path.reload}>{path.error}</Alert> : (
        <div className="dash-hero">
          <NextStep path={path.data} courseId={id} onBuilt={path.reload} />
          <ProgressCard path={path.data} prog={prog.data} courseId={id} />
        </div>
      )}

      <section aria-labelledby="path-title">
        <div className="section-head">
          <h2 id="path-title"><Route className="icon" aria-hidden="true" />Learning path</h2>
          {path.data && <Link className="more" to={`/learn/${id}/path`}>See full path<ChevronRight className="icon-inline" aria-hidden="true" /></Link>}
        </div>
        {path.data ? (
          <>
            <div className="card"><PathChart steps={path.data.steps} nextId={path.data.next_step_id} /></div>
            {path.data.next_step_id && path.data.steps.filter((s) => s.status !== 'done').length > 1 && <><h3 className="small muted mt-6">Coming up after that</h3><PathSteps path={path.data} courseId={id} quietNext limit={3} skipNext /></>}
          </>
        ) : !path.loading && !path.error && (
          <EmptyState icon={Compass} title="No learning path yet" action={<Link className="btn secondary" to={`/learn/${id}/path`}>Start without the diagnostic</Link>}>
            Your path is built after the diagnostic, or you can start with the full course path.
          </EmptyState>
        )}
      </section>

      <section aria-labelledby="prog-title">
        <div className="section-head">
          <h2 id="prog-title"><BarChart3 className="icon" aria-hidden="true" />Mastery by outcome</h2>
          <Link className="more" to={`/learn/${id}/progress`}>Full progress report<ChevronRight className="icon-inline" aria-hidden="true" /></Link>
        </div>
        {prog.loading && !prog.data ? <Loading variant="table" /> : prog.error ? <Alert onRetry={prog.reload}>{prog.error}</Alert> : prog.data && (
          prog.data.clos.length ? <CloMasteryList rows={prog.data.clos} compact /> : <p className="muted">No outcomes published yet.</p>
        )}
      </section>
    </>
  )
}

/** Students land on their next step and a summary, then their path and mastery at a glance. */
function StudentHome() {
  const { data, loading, error, reload } = useLoad(() => api<Course[]>('/diagnostic/courses/mine'))
  const [picked, setPicked] = useState<number | null>(null)
  if (loading) return <Loading variant="cards" />
  if (error) return <Alert onRetry={reload}>{error}</Alert>
  if (!data?.length)
    return (
      <EmptyState icon={BookPlus} title="You're not enrolled in a course yet" action={<Link className="btn" to="/courses">Browse courses</Link>}>
        Enrol in a course to get your diagnostic test and personal learning path.
      </EmptyState>
    )
  const course = data.find((c) => c.id === picked) ?? data[0]
  return (
    <>
      <div className="course-bar">
        {data.length > 1 ? (
          <div className="field m-0">
            <label htmlFor="home-course">Course</label>
            <select id="home-course" value={course.id} onChange={(e) => setPicked(Number(e.target.value))}>
              {data.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
            </select>
          </div>
        ) : <p className="m-0"><span className="chip">{course.code}</span> {course.title}</p>}
      </div>
      <CourseDashboard key={course.id} course={course} />
    </>
  )
}

/** Staff and administrators: their pages grouped as icon tiles with a one-line description. */
function StaffHome({ role }: { role: Role }) {
  const links = routes.filter((r) => r.nav && r.path !== '/' && r.path !== '/account' && r.roles.includes(role))
  const groups = [...new Set(links.map((r) => r.group ?? ''))]
  return (
    <>
      {groups.map((g) => (
        <section key={g} aria-labelledby={`g-${g}`}>
          <div className="section-head"><h2 id={`g-${g}`}>{g || 'General'}</h2></div>
          <div className="link-tiles">
            {links.filter((r) => (r.group ?? '') === g).map((r) => {
              const Icon = NAV_ICON[r.path] ?? Compass
              return (
                <Link key={r.path} to={r.path} className="link-tile">
                  <span className="tile-icon" aria-hidden="true"><Icon className="icon" /></span>
                  <strong>{r.nav}</strong>
                  {NAV_DESC[r.path] && <span className="desc">{NAV_DESC[r.path]}</span>}
                  <ChevronRight className="icon chev" aria-hidden="true" />
                </Link>
              )
            })}
          </div>
        </section>
      ))}
    </>
  )
}

export default function HomePage() {
  const { user } = useAuth()
  if (!user) return null
  const first = user.full_name.replace(/^(Dr|Prof)\.?\s+/i, '').split(/\s+/)[0]
  const student = user.role === 'student'
  if (student) return <Suspense fallback={<Loading variant="cards" />}><StudentCourseHome /></Suspense>
  return (
    <>
      <div className="page-header">
        <div>
          <h1>{greeting()}, {first}</h1>
          <p className="page-sub">{student ? 'Pick up where you left off.' : 'Everything you manage, in one place.'}</p>
        </div>
      </div>
      {student ? <StudentHome /> : <StaffHome role={user.role} />}
    </>
  )
}

