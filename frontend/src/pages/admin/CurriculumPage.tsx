import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, download } from '../../api/client'
import { Alert, Badge, Bar, fmtDate, Loading, useAction, useLoad } from '../../components/ui'
import { elapsed, forgetUpload, rememberUpload, useStoredUpload, useUploadProgress } from '../../components/uploadProgress'
import RoadmapReview, { type RoadmapData } from './RoadmapReview'

export type Issue = { level: 'error' | 'warning' | 'info'; path: string; message: string }
type Clo = { code: string; description: string; unit: number | null }
type Course = { code: string; title: string; credits: number | null; prerequisites: string[]; units: { number: number; title: string; clos: string[] }[]; clos: Clo[]; clo_plo: { clo: string; plo: string }[] }
export type Parsed = { program: { code: string; name: string }; plos: { code: string; description: string }[]; courses: Course[] }
type Version = {
  id: number; program_key: string; version_no: number; title: string; filename: string; size_bytes: number; status: string; parser: string
  extraction_engine: string; uploaded_at: string; approved_at: string | null
  summary: { courses: number; plos: number; clos: number; errors: number; warnings: number; found_at_upload?: number }
  issues_resolved?: boolean
  parsed?: Parsed; warnings?: Issue[]; extracted_markdown?: string
}

export function IssueList({ issues }: { issues: Issue[] }) {
  if (!issues.length) return <Alert kind="success">No problems detected.</Alert>
  return (
    <ul className="stack list-indent">
      {issues.map((w, i) => (
        <li key={i}><Badge value={w.level} tone={w.level === 'error' ? 'bad' : w.level === 'warning' ? 'warn' : ''} /> {w.message}</li>
      ))}
    </ul>
  )
}

export function Outline({ parsed }: { parsed: Parsed }) {
  return (
    <div>
      <p><strong>{parsed.program.code}</strong> — {parsed.program.name}</p>
      <h3>Programme learning outcomes</h3>
      <ul>{parsed.plos.map((p) => <li key={p.code}><strong>{p.code}</strong>: {p.description}</li>)}</ul>
      {parsed.courses.map((c) => (
        <details key={c.code} className="card" open>
          <summary><strong>{c.code}</strong> {c.title} <span className="muted small">· {c.credits ?? '?'} credits · prerequisites: {c.prerequisites.join(', ') || 'none'}</span></summary>
          {c.units.map((u) => (
            <div key={u.number} className="mt-2">
              <strong>Unit {u.number}: {u.title}</strong>
              <ul>
                {c.clos.filter((o) => o.unit === u.number).map((o) => (
                  <li key={o.code}><strong>{o.code}</strong>: {o.description}{' '}
                    {c.clo_plo.filter((m) => m.clo === o.code).map((m) => <Badge key={m.plo} value={m.plo} />)}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {c.clos.filter((o) => !o.unit).map((o) => <p key={o.code} className="small"><Badge value="no unit" tone="bad" /> {o.code}: {o.description}</p>)}
        </details>
      ))}
    </div>
  )
}

type AutoResult = {
  status: string; stopped: string | null; errors?: string[]
  courses: { id: number; code: string; status: string; reason?: string; preparing_questions?: boolean }[]
}

/** What the automatic pipeline did after the upload (automation mode). */
function AutomationResult({ r, onReview }: { r: AutoResult; onReview: () => void }) {
  const active = r.courses.filter((c) => c.status === 'active')
  const waiting = r.courses.filter((c) => c.status !== 'active')
  if (r.stopped) {
    return (
      <Alert kind="warning" title="Needs a person to check">
        {r.stopped}
        {r.errors && <ul className="small list-compact mt-1">{r.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
        <div className="alert-actions"><button type="button" className="secondary small" onClick={onReview}>Open outcome review</button></div>
      </Alert>
    )
  }
  return (
    <>
      {active.length > 0 && (
        <Alert kind="success" title="Curriculum set up automatically">
          Approved and activated: {active.map((c) => c.code).join(', ')}. The AI is drafting diagnostic and practice questions for each course;
          {' '}instructors approve them in the Item bank, and the diagnostic goes live once every CLO has enough approved questions. Next: create sections and assign instructors in Offerings &amp; faculty.
        </Alert>
      )}
      {waiting.length > 0 && (
        <Alert kind="warning" title="Some courses need a person">
          <ul className="small list-compact">{waiting.map((c) => <li key={c.id}><strong>{c.code}</strong>: {c.reason ?? `status ${c.status}`}</li>)}</ul>
          <div className="alert-actions"><Link className="btn secondary small" to="/mappings">Open mappings &amp; activation</Link></div>
        </Alert>
      )}
    </>
  )
}

type UploadResult = Version & { automation?: AutoResult; roadmap?: (RoadmapData & { error?: string }) | null }

/** Live progress of the background upload: what it is doing now and how many courses are extracted so far.
 *  The upload keeps running on the server if you leave this page; coming back picks it up again. */
function UploadProgressCard({ upload, onFinished }: { upload: { id: string; name: string; startedAt: number }; onFinished: (r: UploadResult | null, error: string | null) => void }) {
  const { p, lost, signedOut } = useUploadProgress(upload)
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])
  useEffect(() => {
    if (lost) onFinished(null, 'The upload was interrupted because the server restarted. Upload the file again.')
    else if (p?.done) onFinished((p.result as UploadResult | null) ?? null, p.error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p?.done, lost])
  const total = p?.courses_total ?? null
  return (
    <div className="card" role="status" aria-live="polite">
      {signedOut && <Alert kind="warning" title="You were signed out">The upload keeps running on the server. Sign in again to follow it here and see the result.</Alert>}
      <p className="mt-0"><strong>{p?.message ?? 'Uploading the document'}…</strong> <span className="small muted">({elapsed(upload.startedAt, now)} so far · {upload.name})</span></p>
      {total && !p?.steps ? (
        <>
          <Bar value={(100 * p!.courses_done) / total} label="Courses extracted" />
          <p className="small muted m-0">{p!.courses_done} of {total} courses extracted</p>
        </>
      ) : null}
      {p?.steps ? (
        <>
          <Bar value={(100 * (p.step ?? 0)) / p.steps} label="Courses set up" />
          <p className="small muted m-0">Setting up course {p.step} of {p.steps}</p>
        </>
      ) : null}
      <p className="small muted mb-0">This can take a few minutes. You can use other pages meanwhile — the upload keeps going, and a bar at the top of each page shows how far it has got.</p>
    </div>
  )
}

export default function CurriculumPage({ extraActions }: { extraActions?: (v: Version, reload: () => void) => ReactNode }) {
  const list = useLoad(() => api<Version[]>('/curriculum/versions'))
  const [selected, setSelected] = useState<Version | null>(null)
  const [auto, setAuto] = useState<AutoResult | null>(null)
  const [tab, setTab] = useState<'outline' | 'issues' | 'text'>('outline')
  const [file, setFile] = useState<File | null>(null)
  const [key, setKey] = useState('')
  const [roadFile, setRoadFile] = useState<File | null>(null)
  const upload = useStoredUpload()
  const [failed, setFailed] = useState('')
  const [road, setRoad] = useState<(RoadmapData & { error?: string }) | null>(null)
  const act = useAction()
  const nav = useNavigate()

  async function open(id: number) {
    const v = await act.run(() => api<Version>(`/curriculum/versions/${id}`))
    if (v) setSelected(v)
  }
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    if (roadFile) form.append('roadmap', roadFile)
    if (key) form.append('program_key', key)
    const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `u-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    form.append('upload_id', id)
    setAuto(null)
    setRoad(null)
    setFailed('')
    // The server answers at once and keeps working in the background; progress and result come from the tracker.
    const r = await act.run(() => api<{ upload_id: string }>('/curriculum/upload', { form }))
    if (r) rememberUpload(r.upload_id, file.name)
  }
  function finished(v: UploadResult | null, error: string | null) {
    forgetUpload()
    if (error || !v) { setFailed(error || 'The upload stopped. Try again.'); return }
    setSelected(v)
    setAuto(v.automation ?? null)
    setRoad(v.roadmap ?? null)
    setTab('issues')
    list.reload()
  }
  async function discard(id: number) {
    await act.run(() => api(`/curriculum/versions/${id}/discard`, { method: 'POST' }), 'Preview discarded')
    setSelected(null)
    list.reload()
  }

  return (
    <>
      <h1>Curriculum</h1>
      <p className="muted">Upload a PDF (or DOCX, PPTX, HTML, Markdown, text) with the programme's PLOs and each course's CLOs. The AI extracts them; with automation on, the curriculum is then approved, mapped and activated automatically, and each course's diagnostic and practice questions are drafted for instructors to approve. Anything the AI could not read safely is left for review. Every upload becomes a new version — earlier versions are kept.</p>
      <form className="card" onSubmit={submit}>
        <h2>Upload a curriculum document</h2>
        <div className="grid">
          <div className="field">
            <label htmlFor="cfile">Document</label>
            <input id="cfile" type="file" accept=".pdf,.docx,.pptx,.html,.htm,.md,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
          </div>
          <div className="field">
            <label htmlFor="croad">Semester roadmap (optional)</label>
            <input id="croad" type="file" accept=".pdf,.xlsx,.docx,.md,.txt,.html" onChange={(e) => setRoadFile(e.target.files?.[0] ?? null)} aria-describedby="croad-hint" />
            <p id="croad-hint" className="field-hint">The study plan with Semester 1, 2… columns. Courses are matched to the CLO file by name; you can correct matches after the upload.</p>
          </div>
          <div className="field">
            <label htmlFor="ckey">Programme code (optional)</label>
            <input id="ckey" placeholder="detected from the document" value={key} onChange={(e) => setKey(e.target.value)} />
          </div>
        </div>
        <button disabled={act.busy || !file || !!upload} aria-busy={act.busy || undefined}>{act.busy ? 'Sending the file…' : upload ? 'Upload in progress…' : 'Upload'}</button>
      </form>
      {upload && <UploadProgressCard key={upload.id} upload={upload} onFinished={finished} />}
      {failed && <Alert title="The upload stopped">{failed}</Alert>}
      <Alert>{act.error}</Alert>
      {auto && <AutomationResult r={auto} onReview={() => selected && nav(`/outcomes/review/${selected.id}`)} />}
      {list.error && <Alert onRetry={list.reload}>{list.error}</Alert>}

      {selected && (
        <div className="card">
          <div className="spread">
            <h2 className="m-0">{selected.program_key} v{selected.version_no} <Badge value={selected.status} /></h2>
            <div className="row">
              <button className="secondary" onClick={() => download(`/curriculum/versions/${selected.id}/file`, selected.filename)}>Original file</button>
              {selected.status === 'preview' && (
                <button onClick={async () => { if (await act.run(() => api(`/outcomes/versions/${selected.id}/start-review`, { method: 'POST' }))) nav(`/outcomes/review/${selected.id}`) }}>Start outcome review</button>
              )}
              {['in_review', 'approved'].includes(selected.status) && <button onClick={() => nav(`/outcomes/review/${selected.id}`)}>Open review</button>}
              {selected.status === 'preview' && <button className="danger" onClick={() => discard(selected.id)}>Discard</button>}
              {extraActions?.(selected, () => { list.reload(); open(selected.id) })}
              <button className="secondary" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
          <p className="small muted">{selected.filename} · extracted with {selected.extraction_engine} · parsed by {selected.parser} · {selected.summary.courses} courses, {selected.summary.plos} PLOs, {selected.summary.clos} CLOs</p>
          <div className="tabs" role="group" aria-label="View">
            {(['outline', 'issues', 'text'] as const).map((t) => (
              <button key={t} type="button" aria-pressed={tab === t} onClick={() => setTab(t)}>
                {t === 'outline' ? 'Parsed outline' : t === 'issues' ? (selected.issues_resolved ? `Issues at upload (${selected.summary.found_at_upload ?? 0}, resolved)` : `Issues (${selected.summary.errors + selected.summary.warnings})`) : 'Extracted text'}
              </button>
            ))}
          </div>
          {tab === 'outline' && selected.parsed && <Outline parsed={selected.parsed} />}
          {tab === 'issues' && selected.issues_resolved && <Alert kind="success" title="All issues were resolved before approval">These are the issues found when the file was uploaded. They were fixed or acknowledged in Outcome review, which is required before a curriculum can be approved.</Alert>}
          {tab === 'issues' && <IssueList issues={selected.warnings ?? []} />}
          {tab === 'text' && <pre className="plain" tabIndex={0}>{selected.extracted_markdown}</pre>}
          {road?.error && <Alert kind="warning" title="The roadmap could not be read">{road.error}</Alert>}
          {selected.status !== 'discarded' && <RoadmapReview key={selected.id} versionId={selected.id} initial={road && !road.error && road.version_id === selected.id ? road : null} />}
        </div>
      )}

      <h2>Versions</h2>
      {list.loading ? <Loading variant="table" /> : (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
          <table>
            <thead><tr><th>Programme</th><th>Version</th><th>File</th><th>Status</th><th>Content</th><th>Uploaded</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {list.data?.map((v) => (
                <tr key={v.id}>
                  <td><strong>{v.program_key}</strong><div className="small muted">{v.title}</div></td>
                  <td>v{v.version_no}</td>
                  <td className="small">{v.filename}<div className="muted">{(v.size_bytes / 1024).toFixed(1)} KB</div></td>
                  <td><Badge value={v.status} /></td>
                  <td className="small">{v.summary.courses} courses · {v.summary.clos} CLOs{v.summary.errors > 0 && <div><Badge value={`${v.summary.errors} errors`} tone="bad" /></div>}</td>
                  <td className="small">{fmtDate(v.uploaded_at)}</td>
                  <td><button className="secondary" onClick={() => open(v.id)}>Open</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
