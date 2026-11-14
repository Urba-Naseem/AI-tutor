import { useState } from 'react'
import { api } from '../../api/client'
import { Alert, Badge, fmtDate, Loading, useLoad } from '../../components/ui'

type Ev = { id: number; at: string; category: string; action: string; actor_name: string | null; actor_role: string | null; entity_type: string | null; entity_id: number | null; course_id: number | null; details: Record<string, unknown>; hash: string; request_id: string | null }

export default function AuditPage() {
  const [category, setCategory] = useState('')
  const [action, setAction] = useState('')
  const [rec, setRec] = useState('')
  // record #: one number (1325) or a range (1320-1330)
  const recMatch = rec.trim().match(/^#?\s*(\d+)\s*(?:[-–]\s*#?\s*(\d+))?$/)
  const recBad = rec.trim() !== '' && !recMatch
  const [page, setPage] = useState(0)
  const qs = new URLSearchParams({ limit: '50', offset: String(page * 50) })
  if (category) qs.set('category', category)
  if (action) qs.set('action', action)
  if (recMatch) {
    if (recMatch[2]) { qs.set('record_from', recMatch[1]); qs.set('record_to', recMatch[2]) } else qs.set('record_id', recMatch[1])
  }
  const { data, error, loading } = useLoad(() => api<{ total: number; items: Ev[] }>(`/audit?${qs}`), [category, action, page, recMatch?.[0] ?? ''])
  const chain = useLoad(() => api<{ valid: boolean; checked: number; broken_at?: number; forks?: number[] }>('/audit/verify'))

  return (
    <>
      <h1>Audit &amp; learning events</h1>
      <p className="muted">Append-only, attributable record of decisions and activity. Each record is hash-chained to the previous one.</p>
      {chain.data && (
        <Alert kind={chain.data.valid ? 'success' : 'error'}>
          Integrity check: {chain.data.valid ? `chain intact (${chain.data.checked} records verified)` : `chain BROKEN at record #${chain.data.broken_at} — a record's contents were changed or a record is missing`}
          {chain.data.forks && chain.data.forks.length > 0 && <> No record's contents were changed. {chain.data.forks.length === 1 ? 'Record' : 'Records'} {chain.data.forks.map((x) => `#${x}`).join(', ')} {chain.data.forks.length === 1 ? 'was' : 'were'} saved at the same moment as another record (before the save-order fix), so {chain.data.forks.length === 1 ? 'it links' : 'they link'} to an earlier record.</>}
        </Alert>
      )}
      <div className="row card audit-filters">
        <div className="field min-w-md">
          <label htmlFor="cat">Category</label>
          <select id="cat" value={category} onChange={(e) => { setPage(0); setCategory(e.target.value) }}>
            <option value="">All</option><option>audit</option><option>security</option><option>learning</option><option>ai</option>
          </select>
        </div>
        <div className="field min-w-md">
          <label htmlFor="rec">Record #</label>
          <input id="rec" inputMode="numeric" aria-describedby={recBad ? 'rec-hint' : undefined} aria-invalid={recBad || undefined} placeholder="e.g. 1325 or 1320-1330" value={rec} onChange={(e) => { setPage(0); setRec(e.target.value) }} />
          {recBad && <p id="rec-hint" className="field-error" role="alert">Type a record number, or a range like 1320-1330.</p>}
        </div>
        <div className="field min-w-lg">
          <label htmlFor="act">Action starts with</label>
          <input id="act" placeholder="e.g. auth. or curriculum." value={action} onChange={(e) => { setPage(0); setAction(e.target.value) }} />
        </div>
      </div>
      <Alert>{error}</Alert>
      {loading ? <Loading variant="table" /> : (
        <>
          <p className="small muted">{data?.total} events</p>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Table (scroll sideways if it does not fit)">
            <table>
              <thead><tr><th>#</th><th>When</th><th>Category</th><th>Action</th><th>Actor</th><th>Entity</th><th>Details</th></tr></thead>
              <tbody>
                {data?.items.map((e) => (
                  <tr key={e.id}>
                    <td className="num"><strong>#{e.id}</strong></td>
                    <td className="small">{fmtDate(e.at)}<div className="muted">hash {e.hash}</div></td>
                    <td><Badge value={e.category} /></td>
                    <td><code>{e.action}</code></td>
                    <td>{e.actor_name ?? 'system'}<div className="small muted">{e.actor_role}</div></td>
                    <td className="small">{e.entity_type ? `${e.entity_type} #${e.entity_id ?? ''}` : '—'}{e.course_id ? <div className="muted">course #{e.course_id}</div> : null}</td>
                    <td className="small"><code className="break-all">{JSON.stringify(e.details)}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row mt-2">
            <button className="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="secondary" disabled={(page + 1) * 50 >= (data?.total ?? 0)} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </>
      )}
    </>
  )
}
