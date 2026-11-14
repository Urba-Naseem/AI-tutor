import { api } from '../api/client'
import { askConfirm } from './dialogApi'
import { Alert, Badge, fmtDate, Loading, useAction, useLoad } from './ui'

type C = { current_version: string; consented: boolean; history: { version: string; accepted_at: string; withdrawn_at: string | null }[] }

export default function ConsentPanel() {
  const c = useLoad(() => api<C>('/auth/my-consent'))
  const text = useLoad(() => api<{ text: string; version: string }>('/auth/consent'))
  const act = useAction()
  if (c.loading && !c.data) return <div className="card"><Loading /></div>
  if (!c.data) return <Alert>{c.error && `We couldn't load your consent status: ${c.error}`}</Alert>
  return (
    <div className="card">
      <h2 className="mt-0">Data consent <Badge value={c.data.consented ? 'given' : 'not given'} tone={c.data.consented ? 'ok' : 'bad'} /></h2>
      <details><summary className="small">Read the consent statement (v{text.data?.version})</summary><pre className="plain" tabIndex={0}>{text.data?.text}</pre></details>
      <ul className="small">{c.data.history.map((h, i) => <li key={i}>v{h.version} accepted {fmtDate(h.accepted_at)}{h.withdrawn_at && ` · withdrawn ${fmtDate(h.withdrawn_at)}`}</li>)}</ul>
      <Alert>{act.error}</Alert>
      {c.data.consented ? (
        <button className="danger" onClick={async () => { if (await askConfirm({ title: 'Withdraw data consent?', message: 'All learning features (diagnostic, quizzes, tutor, learning path) will be paused until you accept consent again.', confirmLabel: 'Withdraw consent', danger: true }) &&(await act.run(() => api('/auth/my-consent/withdraw', { method: 'POST' })))) c.reload() }}>Withdraw consent</button>
      ) : (
        <button onClick={async () => { if (await act.run(() => api('/auth/my-consent/accept', { body: { consent_version: c.data!.current_version } }))) c.reload() }}>Accept current consent</button>
      )}
    </div>
  )
}
