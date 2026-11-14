/**
 * Learning path map (brief §5b-A), hand-built SVG + HTML nodes - no graph library.
 * Left-to-right, one column per unit; steps stacked in the column; reteach / remedial steps branch to the side
 * as a dashed loop. Done = green, current = action blue with glow ("You are here"), upcoming = grey dashed,
 * escalated / skipped = amber. Narrow containers switch to a top-to-bottom layout. Every node is a button
 * (keyboard: Tab + Enter) that opens a side panel with the step's reason.
 */
import { BookOpen, ClipboardCheck, HelpCircle, Layers, Lock, Maximize2, Minus, Plus, RotateCcw, type LucideIcon } from 'lucide-react'
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Button, Drawer, ScoreRing, StatusPill } from './Kit'

export type PathNodeKind = 'diagnostic' | 'lesson' | 'quiz' | 'reteach' | 'remedial'
export type PathNodeStatus = 'done' | 'current' | 'upcoming' | 'escalated' | 'skipped'
export type PathNode = {
  id: string | number; unit: number; unitTitle: string; kind: PathNodeKind; clo: string; title: string; status: PathNodeStatus
  score?: number | null; threshold: number; attained?: boolean | null; reason: string
  branchOf?: string | number; loopLabel?: string; href?: string; history?: { label: string; score: number }[]
}

const KIND: Record<PathNodeKind, [LucideIcon, string]> = {
  diagnostic: [ClipboardCheck, 'Diagnostic'], lesson: [BookOpen, 'Lesson'], quiz: [HelpCircle, 'Quiz'], reteach: [RotateCcw, 'Reteach'], remedial: [Layers, 'Remedial'],
}
const STATUS_WORD: Record<PathNodeStatus, string> = { done: 'completed', current: 'you are here', upcoming: 'coming up', escalated: 'escalated to your instructor', skipped: 'skipped' }
// Layout constants (px in map space; the map scales as a whole)
const W = 236, H = 76, GX = 60, GY = 46, PAD = 24, HEAD = 48, COL_GAP = 24

type Placed = PathNode & { x: number; y: number }
type Col = { unit: number; title: string; x: number; y: number; w: number; h: number; status: 'Done' | 'In progress' | '' }

function layout(nodes: PathNode[], vertical: boolean) {
  const units = [...new Set(nodes.map((n) => n.unit))]
  const placed: Placed[] = []
  const cols: Col[] = []
  let cursor = 0
  for (const u of units) {
    const inUnit = nodes.filter((n) => n.unit === u)
    const main = inUnit.filter((n) => n.branchOf == null)
    const branches = inUnit.filter((n) => n.branchOf != null)
    const done = inUnit.every((n) => n.status === 'done' || n.status === 'skipped')
    const started = inUnit.some((n) => n.status !== 'upcoming')
    const status = done ? 'Done' : started ? 'In progress' : ''
    if (!vertical) {
      const w = PAD * 2 + W + (branches.length ? GX + W : 0)
      main.forEach((n, i) => placed.push({ ...n, x: cursor + PAD, y: HEAD + i * (H + GY) }))
      branches.forEach((n) => {
        const parent = placed.find((p) => p.id === n.branchOf)
        placed.push({ ...n, x: cursor + PAD + W + GX, y: parent ? parent.y : HEAD })
      })
      const h = HEAD + Math.max(main.length, 1) * (H + GY) - GY + PAD
      cols.push({ unit: u, title: inUnit[0].unitTitle, x: cursor, y: 0, w, h, status })
      cursor += w + COL_GAP
    } else {
      // top-to-bottom: units stacked; a branch sits right under the step it loops from, indented
      let y = cursor + HEAD
      for (const n of main) {
        placed.push({ ...n, x: PAD, y }); y += H + GY
        for (const b of branches.filter((x) => x.branchOf === n.id)) { placed.push({ ...b, x: PAD + 28, y }); y += H + GY }
      }
      const h = y - cursor - GY + PAD
      cols.push({ unit: u, title: inUnit[0].unitTitle, x: 0, y: cursor, w: PAD * 2 + W + 28, h, status })
      cursor += h + COL_GAP
    }
  }
  const width = vertical ? PAD * 2 + W + 28 : cursor - COL_GAP
  const height = vertical ? cursor - COL_GAP : Math.max(...cols.map((c) => c.h), 0)
  return { placed, cols, width, height }
}

export function PathMap({ nodes, locked, onGo }: { nodes: PathNode[]; locked?: boolean; onGo?: (n: PathNode) => void }) {
  const outer = useRef<HTMLDivElement>(null)
  const [vertical, setVertical] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [open, setOpen] = useState<PathNode | null>(null)
  const { placed, cols, width, height } = layout(nodes, vertical)

  // orientation + fit-to-view from the container width
  useLayoutEffect(() => {
    const el = outer.current
    if (!el) return
    const fit = () => {
      const v = el.clientWidth < 520
      setVertical(v)
      const lay = layout(nodes, v)
      setZoom(Math.min(1, Math.max(0.5, (el.clientWidth - 16) / lay.width)))
    }
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(el)
    return () => ro.disconnect()
  }, [nodes])
  // centre the current step on load
  useEffect(() => {
    const el = outer.current
    const cur = placed.find((p) => p.status === 'current')
    if (!el || !cur) return
    el.scrollLeft = Math.max(0, (cur.x + W / 2) * zoom - el.clientWidth / 2)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vertical])

  const byId = new Map(placed.map((p) => [p.id, p]))
  const mainOrder = placed.filter((p) => p.branchOf == null)
  const edges: ReactNode[] = []
  mainOrder.forEach((a, i) => {
    const b = mainOrder[i + 1]
    if (!b) return
    const solid = a.status === 'done' || a.status === 'skipped'
    let d: string
    if (vertical || a.unit === b.unit) d = `M ${a.x + W / 2} ${a.y + H} L ${b.x + W / 2} ${b.y - 6}`
    else { const sx = a.x + W, sy = a.y + H / 2, ex = b.x - 6, ey = b.y + H / 2; d = `M ${sx} ${sy} C ${sx + 40} ${sy}, ${ex - 40} ${ey}, ${ex} ${ey}` }
    edges.push(<path key={`e${a.id}`} d={d} className={`pedge${solid ? ' is-solid' : ''}`} markerEnd={`url(#${solid ? 'arr-solid' : 'arr-dash'})`} />)
  })
  for (const n of placed.filter((p) => p.branchOf != null)) {
    const p = byId.get(n.branchOf!)
    if (!p) continue
    const back = n.status === 'done'
    let out: string, ret: string, lx: number, ly: number
    if (vertical) {
      out = `M ${p.x + 12} ${p.y + H} C ${p.x + 4} ${p.y + H + GY / 2}, ${n.x - 12} ${n.y}, ${n.x} ${n.y + H / 2}`
      ret = `M ${n.x + W} ${n.y + H / 2} C ${n.x + W + 20} ${n.y}, ${p.x + W + 20} ${p.y + H}, ${p.x + W} ${p.y + H / 2}`
      lx = n.x + W - 60; ly = n.y - 10
    } else {
      out = `M ${p.x + W} ${p.y + H * 0.35} C ${p.x + W + 28} ${p.y + H * 0.1}, ${n.x - 28} ${n.y + H * 0.1}, ${n.x - 6} ${n.y + H * 0.35}`
      ret = `M ${n.x} ${n.y + H * 0.7} C ${n.x - 28} ${n.y + H * 0.95}, ${p.x + W + 28} ${p.y + H * 0.95}, ${p.x + W + 6} ${p.y + H * 0.7}`
      lx = (p.x + W + n.x) / 2; ly = p.y - 8
    }
    edges.push(<path key={`b${n.id}`} d={out} className="pedge is-loop" markerEnd="url(#arr-loop)" />)
    edges.push(<path key={`r${n.id}`} d={ret} className={`pedge is-loop${back ? ' is-back' : ''}`} markerEnd="url(#arr-loop)" />)
    if (n.loopLabel) edges.push(<foreignObject key={`l${n.id}`} x={lx - 70} y={ly - 14} width={140} height={26}><span className="pedge-label">{n.loopLabel}</span></foreignObject>)
  }

  const summary = `${nodes.filter((n) => n.status === 'done').length} of ${nodes.length} steps done; current: ${nodes.find((n) => n.status === 'current')?.title ?? 'none'}.`
  return (
    <div className="pmap-wrap">
      {locked && <p className="pmap-locked"><Lock className="icon-inline" aria-hidden="true" /> Path locked by your instructor: automatic changes are paused.</p>}
      <div className="pmap" ref={outer} role="group" aria-label={`Learning path map. ${summary} Use Tab to move between steps and Enter to see why a step is there.`}>
        <div className="pmap-sizer" style={{ width: width * zoom, height: height * zoom }}>
          <div className="pmap-canvas" style={{ width, height, transform: `scale(${zoom})` }}>
            <svg className="pmap-svg" width={width} height={height} aria-hidden="true">
              <defs>
                {['solid', 'dash', 'loop'].map((k) => (
                  <marker key={k} id={`arr-${k}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                    <path d="M0,0 L10,5 L0,10 z" className={`parrow parrow-${k}`} />
                  </marker>
                ))}
              </defs>
              {cols.map((c) => <rect key={c.unit} x={c.x} y={c.y} width={c.w} height={c.h} rx={10} className="pcol" />)}
              {edges}
            </svg>
            {cols.map((c) => (
              <div key={`h${c.unit}`} className="pcol-head" style={{ left: c.x + PAD, top: c.y + 14, width: c.w - PAD * 2 }}>
                <span className="pcol-name">Unit {c.unit} · {c.title}</span><span className={`pcol-status ${c.status === 'Done' ? 'tone-good' : 'tone-action'}`}>{c.status}</span>
              </div>
            ))}
            {placed.map((n) => {
              const [Icon, kindLabel] = KIND[n.kind]
              return (
                <button key={n.id} type="button" className={`pnode is-${n.status} kind-${n.kind}`} style={{ left: n.x, top: n.y, width: W, height: H }}
                  onClick={() => setOpen(n)} aria-label={`${kindLabel}, ${n.clo}: ${n.title}. ${STATUS_WORD[n.status]}${n.score != null ? `, score ${Math.round(n.score)}%` : ''}. Open details.`}>
                  <span className="pnode-icon" aria-hidden="true"><Icon /></span>
                  <span className="pnode-text" aria-hidden="true"><span className="pnode-kind">{kindLabel} · {n.clo}</span><span className="pnode-title">{n.title}</span></span>
                  {n.score != null && <span className="pnode-ring" aria-hidden="true"><ScoreRing value={n.score} threshold={n.threshold} attained={n.attained} size={34} /></span>}
                  {n.status === 'current' && <span className="pnode-here" aria-hidden="true">You are here</span>}
                </button>
              )
            })}
          </div>
        </div>
        <div className="pmap-zoom">
          <button type="button" className="kicon-btn" aria-label="Zoom in" title="Zoom in" onClick={() => setZoom((z) => Math.min(1.6, z + 0.15))}><Plus aria-hidden="true" /></button>
          <button type="button" className="kicon-btn" aria-label="Zoom out" title="Zoom out" onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}><Minus aria-hidden="true" /></button>
          <button type="button" className="kicon-btn" aria-label="Fit to view" title="Fit to view" onClick={() => outer.current && setZoom(Math.min(1, Math.max(0.4, (outer.current.clientWidth - 16) / width)))}><Maximize2 aria-hidden="true" /></button>
        </div>
      </div>
      <ul className="pmap-legend" aria-label="Map legend">
        <li><span className="lg-node is-done" aria-hidden="true" />Completed</li>
        <li><span className="lg-node is-current" aria-hidden="true" />You are here</li>
        <li><span className="lg-node is-upcoming" aria-hidden="true" />Coming up</li>
        <li><span className="lg-node is-reteach" aria-hidden="true" />Reteach (extra practice)</li>
        <li><span className="lg-loop" aria-hidden="true" />Adaptation loop</li>
        <li><ScoreRing value={72} threshold={60} size={18} /> Score ring · red mark = target</li>
      </ul>
      <p className="sr-only">{summary}</p>
      <Drawer open={!!open} onClose={() => setOpen(null)} title={open ? `${KIND[open.kind][1]} · ${open.clo}: ${open.title}` : ''}
        footer={open && onGo && open.status !== 'done' && open.href ? <Button onClick={() => { onGo(open); setOpen(null) }}>Go to step</Button> : open && open.status === 'upcoming' ? <p className="small muted m-0">Locked — finish the earlier steps first.</p> : undefined}>
        {open && (
          <div className="pmap-panel">
            <StatusPill status={open.status === 'current' ? 'current' : open.status === 'upcoming' ? 'upcoming' : open.status} />
            <h3>Why this step is here</h3>
            <p>{open.reason}</p>
            {open.score != null && <p className="tabular"><strong>Latest score:</strong> {Math.round(open.score)}% (target {open.threshold}%)</p>}
            {open.history?.length ? (
              <>
                <h3>Mastery history</h3>
                <ol className="pmap-history">{open.history.map((h, i) => <li key={i}><span>{h.label}</span><span className="tabular">{h.score}%</span></li>)}</ol>
              </>
            ) : null}
          </div>
        )}
      </Drawer>
    </div>
  )
}
