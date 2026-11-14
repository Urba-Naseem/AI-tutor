import { api } from '../api/client'
import { Alert, useLoad } from './ui'

/** Tells staff when automation is on: AI output is published at once and their review is optional. */
export default function AutomationNote({ what, needsApproval }: { what: string; needsApproval?: boolean }) {
  const s = useLoad(() => api<{ automation?: boolean }>('/ai/status'))
  if (!s.data?.automation) return null
  return (
    <Alert kind="info" title="Automation is on">
      {needsApproval
        ? <>{what} are drafted by the AI automatically, but students only see them after you approve the questionnaire: review the drafts, delete any you don't want, then approve them all once at the end. The diagnostic then goes live by itself.</>
        : <>{what} are published automatically as soon as the AI writes them. Your review is optional: check them here and retire, edit or replace anything that is wrong.</>}
    </Alert>
  )
}
