/** TEMPORARY review page (brief §9 step 3): every kit component and state with sample data. Remove before release. */
import { ArrowRight, Download } from 'lucide-react'
import { useState } from 'react'
import { AttainmentByOutcome, MasteryMultiples, MasteryOverTime, PathDistribution, type CloSeries } from '../components/kit/Charts'
import { Button, Card, DataTable, Drawer, Field, MasteryBar, Modal, OutcomeRow, ProgressRing, ScoreRing, Segmented, Skeleton, StatTile, StatusPill, Stepper, Tabs, Timeline } from '../components/kit/Kit'
import { PathMap, type PathNode } from '../components/kit/PathMap'

const T = 60
const NODES: PathNode[] = [
  { id: 1, unit: 1, unitTitle: 'Basics', kind: 'diagnostic', clo: 'CLO 1', title: 'Readiness check', status: 'done', score: 41, threshold: T, reason: 'Everyone starts with the diagnostic so the path can fit what you already know.' },
  { id: 2, unit: 1, unitTitle: 'Basics', kind: 'lesson', clo: 'CLO 1', title: 'Variables & types', status: 'done', threshold: T, reason: 'Your diagnostic score for CLO 1 was 41% (below 60%), so you study the lesson first.' },
  { id: 3, unit: 1, unitTitle: 'Basics', kind: 'quiz', clo: 'CLO 1', title: 'Variables practice', status: 'done', score: 78, threshold: T, reason: 'Practise CLO 1 until you reach the 60% target.', history: [{ label: 'Diagnostic', score: 41 }, { label: 'Quiz 1', score: 78 }] },
  { id: 4, unit: 2, unitTitle: 'Control flow', kind: 'lesson', clo: 'CLO 2', title: 'If / else decisions', status: 'done', threshold: T, reason: 'Unit 2 builds on unit 1.' },
  { id: 5, unit: 2, unitTitle: 'Control flow', kind: 'quiz', clo: 'CLO 2', title: 'Selection practice', status: 'done', score: 72, threshold: T, reason: 'Practise CLO 2. Your first try was 48%, so a reteach was added; the retry scored 72%.' },
  { id: 51, unit: 2, unitTitle: 'Control flow', kind: 'reteach', clo: 'CLO 2', title: 'New explanation', status: 'done', score: 58, threshold: T, branchOf: 5, loopLabel: 'Reteach 1/3', reason: 'You scored 48% on CLO 2 (below 60%): a different explanation, then a retry.' },
  { id: 6, unit: 2, unitTitle: 'Control flow', kind: 'lesson', clo: 'CLO 3', title: 'Loops: for & while', status: 'current', threshold: T, reason: 'You reached 72% on CLO 2, so you move on to CLO 3.' },
  { id: 7, unit: 3, unitTitle: 'Functions', kind: 'quiz', clo: 'CLO 3', title: 'Loop practice', status: 'upcoming', threshold: T, reason: 'Practise CLO 3 after the lesson.' },
  { id: 8, unit: 3, unitTitle: 'Functions', kind: 'lesson', clo: 'CLO 4', title: 'Writing functions', status: 'upcoming', threshold: T, reason: 'Unit 3 comes after unit 2.' },
  { id: 9, unit: 3, unitTitle: 'Functions', kind: 'quiz', clo: 'CLO 4', title: 'Functions practice', status: 'escalated', score: 30, threshold: T, reason: 'Three tries below 60%: your instructor has been asked to help.' },
  { id: 10, unit: 4, unitTitle: 'Arrays', kind: 'lesson', clo: 'CLO 5', title: 'Arrays & strings', status: 'upcoming', threshold: T, reason: 'Unit 4 comes last.' },
  { id: 11, unit: 4, unitTitle: 'Arrays', kind: 'quiz', clo: 'CLO 5', title: 'Arrays practice', status: 'upcoming', threshold: T, reason: 'Practise CLO 5.' },
]
const SERIES: CloSeries[] = [
  { clo: 'CLO 1', description: 'Use variables and data types', threshold: T, points: [{ label: 'Diagnostic', date: '2 Oct', activity: 'Diagnostic', score: 41 }, { label: 'Quiz', date: '6 Oct', activity: 'Quiz', score: 78, detail: '4 / 5 correct · 0 hints' }] },
  { clo: 'CLO 2', description: 'Use selection and repetition to control program flow', threshold: T, points: [
    { label: 'Diagnostic', date: '2 Oct', activity: 'Diagnostic', score: 35 }, { label: 'Quiz', date: '9 Oct', activity: 'Quiz', score: 48, event: 'Reteach assigned' },
    { label: 'Reteach', date: '12 Oct', activity: 'Reteach', score: 58 }, { label: 'Quiz retry', date: '14 Oct', activity: 'Quiz', score: 66, event: 'Advanced to CLO 3' },
    { label: 'Quiz 20 Oct', date: '20 Oct', activity: 'Quiz', score: 72, detail: '3 / 3 correct · 1 hint used' }] },
  { clo: 'CLO 3', description: 'Repetition with loops', threshold: T, points: [{ label: 'Diagnostic', date: '2 Oct', activity: 'Diagnostic', score: 52 }] },
  { clo: 'CLO 4', description: 'Write and call functions', threshold: T, points: [{ label: 'Diagnostic', date: '2 Oct', activity: 'Diagnostic', score: 30 }] },
  { clo: 'CLO 5', description: 'Work with arrays and strings', threshold: T, points: [] },
]
const DIST = [
  { step: 'Diag', unit: 'Unit 1 · Basics', onTrack: 2, reteach: 0, escalated: 0 }, { step: 'L1', unit: 'Unit 1 · Basics', onTrack: 1, reteach: 0, escalated: 0 },
  { step: 'Q1', unit: 'Unit 1 · Basics', onTrack: 2, reteach: 0, escalated: 0 }, { step: 'L2', unit: 'Unit 2 · Control flow', onTrack: 3, reteach: 0, escalated: 0 },
  { step: 'Q2', unit: 'Unit 2 · Control flow', onTrack: 4, reteach: 2, escalated: 0 }, { step: 'L3', unit: 'Unit 2 · Control flow', onTrack: 5, reteach: 0, escalated: 0 },
  { step: 'Q3', unit: 'Unit 2 · Control flow', onTrack: 3, reteach: 5, escalated: 2 }, { step: 'L4', unit: 'Unit 3 · Functions', onTrack: 2, reteach: 0, escalated: 0 },
  { step: 'Q4', unit: 'Unit 3 · Functions', onTrack: 1, reteach: 0, escalated: 0 }, { step: 'L5', unit: 'Unit 4 · Arrays', onTrack: 0, reteach: 0, escalated: 0 },
]
const ATT = [
  { clo: 'CLO 1', name: 'Variables', attained: 81, near: 11, notAttained: 3, insufficient: 5, average: 74, threshold: T },
  { clo: 'CLO 2', name: 'Selection', attained: 63, near: 19, notAttained: 12, insufficient: 6, average: 64, threshold: T },
  { clo: 'CLO 3', name: 'Loops', attained: 31, near: 28, notAttained: 22, insufficient: 19, average: 51, threshold: T },
  { clo: 'CLO 4', name: 'Functions', attained: 12, near: 9, notAttained: 16, insufficient: 63, average: 43, threshold: T },
  { clo: 'CLO 5', name: 'Arrays', attained: 0, near: 3, notAttained: 6, insufficient: 91, average: null, threshold: T },
]
type Row = { name: string; id: string; role: string; status: string; last: number }
const ROWS: Row[] = [
  { name: 'Hamza Ali', id: '21-CS-003', role: 'Student', status: 'escalated', last: 2 },
  { name: 'Zainab Raza', id: '21-CS-019', role: 'Student', status: 'pending', last: 1 },
  { name: 'Sara Khan', id: '21-CS-014', role: 'Student', status: 'attained', last: 0 },
]

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="sg-section"><h2>{title}</h2>{children}</section>
}

export default function StyleguidePage() {
  const [view, setView] = useState<'map' | 'list'>('map')
  const [modal, setModal] = useState(false)
  const [drawer, setDrawer] = useState(false)
  return (
    <>
      <div className="phead">
        <div>
          <p className="phead-crumb">Design / Styleguide (temporary)</p>
          <h1>Component styleguide</h1>
          <p className="phead-desc">Every component and state from the design brief, with sample data.</p>
        </div>
        <div className="phead-actions">
          <Segmented label="View" options={[{ value: 'map', label: 'Map' }, { value: 'list', label: 'List' }]} value={view} onChange={setView} />
          <Button icon={<ArrowRight aria-hidden="true" />}>Continue: Loops lesson</Button>
        </div>
      </div>

      <Section title="Buttons">
        <div className="sg-row">
          <Button>Primary</Button><Button variant="secondary">Secondary</Button><Button variant="ghost">Ghost</Button><Button variant="danger">Danger</Button>
          <Button size="sm">Small</Button><Button loading>Saving…</Button><Button disabled>Disabled</Button>
          <Button variant="secondary" icon={<Download aria-hidden="true" />}>Download report</Button>
        </div>
      </Section>

      <Section title="Stat tiles">
        <div className="ktiles">
          <StatTile label="Outcomes attained" value="2" suffix="/ 5" context="+1 this week" contextTone="good" />
          <StatTile label="Average mastery" value="64%" bar={{ value: 64, threshold: T }} />
          <StatTile label="Path progress" value="6" suffix="/ 12 steps" context="Next: Loops lesson (CLO 3)" />
          <StatTile label="Open escalations" value={<span className="tone-bad">3</span>} context="Oldest waiting 2 days" />
        </div>
      </Section>

      <Section title="Mastery bar - every state (target 60%)">
        <div className="sg-bars">
          {([['Attained · 78%', 78], ['Near · 52% (within 15 points)', 52], ['Not attained · 30%', 30], ['Not enough evidence', null], ['Exactly at target · 60%', 60]] as const).map(([l, v]) => (
            <div key={l}><p className="small">{l}</p><MasteryBar value={v} threshold={T} label={l} size="md" /></div>
          ))}
          <div><p className="small">Sizes: sm · md · lg</p><MasteryBar value={72} threshold={T} size="sm" label="sm" /><MasteryBar value={72} threshold={T} size="md" label="md" /><MasteryBar value={72} threshold={T} size="lg" label="lg" /></div>
        </div>
      </Section>

      <Section title="Rings and pills">
        <div className="sg-row">
          <ScoreRing value={78} threshold={T} size={44} label="CLO 1" /><ScoreRing value={52} threshold={T} size={44} label="CLO 3" /><ScoreRing value={30} threshold={T} size={44} label="CLO 4" /><ScoreRing value={null} threshold={T} size={44} label="CLO 5" />
          <ProgressRing done={6} total={12} />
        </div>
        <div className="sg-row">
          {['attained', 'near', 'not_attained', 'insufficient', 'approved', 'pending', 'draft', 'rejected', 'escalated', 'current'].map((s) => <StatusPill key={s} status={s} />)}
        </div>
      </Section>

      <div className="grid12">
        <Card className="span-12" title="Your learning path" subtitle="Version 4 · adapted 14 Oct after your CLO 2 quiz · click a step to see why it's there" action={<StatusPill status="on_track" />}>
          {view === 'map' ? <PathMap nodes={NODES} onGo={() => undefined} /> : (
            <Stepper steps={NODES.filter((n) => n.branchOf == null).slice(0, 7).map((n) => ({ id: n.id, title: n.title, meta: `${n.kind} · ${n.clo}`, reason: n.reason, status: n.status === 'done' ? 'done' : n.status === 'current' ? 'current' : 'upcoming' }))} />
          )}
        </Card>
        <Card className="span-6" title="Your outcomes" subtitle="Target: 60% · based on your latest attempts">
          <div className="orows">
            <OutcomeRow code="CLO 1" description="Use variables and data types" value={78} note="Updated this week" />
            <OutcomeRow code="CLO 2" description="Control flow with selection" value={72} note="Updated this week" />
            <OutcomeRow code="CLO 3" description="Repetition with loops" value={52} note="Updated this week" />
            <OutcomeRow code="CLO 4" description="Write and call functions" value={30} note="From diagnostic" />
            <OutcomeRow code="CLO 5" description="Work with arrays and strings" value={null} note="Diagnostic only" />
          </div>
        </Card>
      </div>

      <Section title="Locked path map">
        <Card><PathMap nodes={NODES.slice(0, 5)} locked /></Card>
      </Section>

      <div className="grid12">
        <Card className="span-6" title="Mastery over time"><MasteryOverTime series={SERIES} /></Card>
        <Card className="span-5" title="Mastery per outcome (small multiples)"><MasteryMultiples series={SERIES} /></Card>
        <Card className="span-7" title="Where students are on the path" subtitle="Current step of each student · click a bar to see who"><PathDistribution data={DIST} onSelect={() => undefined} /></Card>
        <Card className="span-5" title="Recent path changes" subtitle="Automatic adaptations and your overrides">
          <Timeline events={[
            { id: 1, tone: 'bad', title: 'Hamza Ali · escalated', detail: '3 failed rounds on CLO 3 → moved on to CLO 4, flagged for you', when: 'Today 10:12' },
            { id: 2, tone: 'action', title: "You overrode Bilal S.'s path", detail: 'Skipped reteach on CLO 2 · “Showed mastery in lab work”', when: 'Yesterday' },
            { id: 3, tone: 'near', title: 'Sara Khan · reteach added', detail: 'CLO 2 quiz 48% → reteach round 1 of 3', when: 'Yesterday' },
            { id: 4, tone: 'good', title: 'Sara Khan · advanced', detail: 'CLO 2 reached 66% → moved on to CLO 3', when: '14 Oct' },
            { id: 5, tone: 'neutral', title: "You locked Ali R.'s path", detail: 'Automatic changes paused · “Following a study plan”', when: '13 Oct' },
          ]} />
        </Card>
        <Card className="span-12" title="Attainment by outcome" subtitle="Share of students in each status · average on the right"><AttainmentByOutcome rows={ATT} /></Card>
      </div>

      <Section title="Table (sortable, row actions, empty state)">
        <DataTable<Row> caption="Students" rows={ROWS} rowKey={(r) => r.id}
          columns={[
            { key: 'name', header: 'Name', sort: (r) => r.name, render: (r) => <strong>{r.name}</strong> },
            { key: 'id', header: 'Student ID', render: (r) => r.id },
            { key: 'status', header: 'Status', sort: (r) => r.status, render: (r) => <StatusPill status={r.status} /> },
            { key: 'last', header: 'Days waiting', align: 'right', sort: (r) => r.last, render: (r) => r.last },
          ]}
          actions={(r) => [{ label: `Open ${r.name}`, onSelect: () => undefined }, { label: 'Remove', onSelect: () => undefined, danger: true }]} />
        <div className="mt-6"><DataTable<Row> caption="Empty" rows={[]} rowKey={(r) => r.id} columns={[]} empty="No students yet — they appear here once they enrol." /></div>
      </Section>

      <div className="grid12">
        <Card className="span-6" title="Form fields">
          <Field label="Full name" required help="As it appears on your student card.">{(a) => <input {...a} />}</Field>
          <Field label="E-mail" required error="Enter an e-mail address ending in university.edu.">{(a) => <input {...a} defaultValue="sara@gmail" />}</Field>
          <Field label="Reason">{(a) => <textarea {...a} rows={3} />}</Field>
        </Card>
        <Card className="span-6" title="Tabs, modal, drawer, skeleton" ruled>
          <Tabs label="Example tabs" tabs={[{ id: 'a', label: 'Overview', content: <p>Tab content one.</p> }, { id: 'b', label: 'History', content: <p>Tab content two.</p> }]} />
          <div className="sg-row"><Button variant="secondary" onClick={() => setModal(true)}>Open modal</Button><Button variant="secondary" onClick={() => setDrawer(true)}>Open drawer</Button></div>
          <Skeleton lines={3} />
        </Card>
      </div>
      <Modal open={modal} onClose={() => setModal(false)} title="Reject this question?" footer={<><Button variant="secondary" onClick={() => setModal(false)}>Cancel</Button><Button variant="danger" onClick={() => setModal(false)}>Reject question</Button></>}>
        <Field label="Reason" required>{(a) => <textarea {...a} rows={3} />}</Field>
      </Modal>
      <Drawer open={drawer} onClose={() => setDrawer(false)} title="Edit offering"><p>Side drawer for create / edit forms.</p></Drawer>
    </>
  )
}
