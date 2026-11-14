/**
 * Status codes -> friendly text and tone, in ONE place (brief §6). Screens never print raw codes like
 * `not_attained` or `insufficient`; they pass the code here.
 */
export type Tone = 'good' | 'near' | 'bad' | 'neutral' | 'action'

const MAP: Record<string, [string, Tone]> = {
  attained: ['Attained', 'good'], mastered: ['Attained', 'good'], ready: ['Ready', 'good'], approved: ['Approved', 'good'],
  done: ['Done', 'good'], completed: ['Completed', 'good'], active: ['Active', 'good'], published: ['Published', 'good'],
  resolved: ['Resolved', 'good'], upheld: ['Upheld', 'good'], verified: ['Verified', 'good'], enrolled: ['Enrolled', 'good'],
  on_track: ['Path on track', 'good'], chain_intact: ['Chain intact', 'good'],
  near: ['Needs practice', 'near'], developing: ['Needs practice', 'near'], below: ['Needs practice', 'near'],
  pending: ['Pending review', 'near'], in_review: ['In review', 'near'], draft: ['Draft', 'near'], suggested: ['Suggested', 'near'],
  in_progress: ['In progress', 'near'], open: ['Open', 'near'], submitted: ['Submitted', 'near'], appeal: ['Appeal', 'near'],
  review: ['Review', 'near'], reteach: ['In reteach', 'near'], preview: ['Preview', 'near'], locked: ['Locked', 'near'],
  not_attained: ['Not attained', 'bad'], not_ready: ['Not attained', 'bad'], rejected: ['Rejected', 'bad'], escalated: ['Escalated', 'bad'],
  error: ['Error', 'bad'], withdrawn: ['Withdrawn', 'bad'], blocked: ['Blocked', 'bad'], retired: ['Retired', 'bad'],
  tampering: ['Tampering detected', 'bad'],
  insufficient: ['Not enough evidence yet', 'neutral'], not_started: ['Not enough evidence yet', 'neutral'], none: ['Not enough evidence yet', 'neutral'],
  upcoming: ['Coming up', 'neutral'], report: ['Report', 'neutral'], superseded: ['Superseded', 'neutral'], discarded: ['Discarded', 'neutral'],
  current: ['You are here', 'action'], up_next: ['Up next', 'action'],
}

export function statusText(code: string | null | undefined): string {
  if (!code) return MAP.insufficient[0]
  const k = code.toLowerCase().replace(/[\s-]+/g, '_')
  return MAP[k]?.[0] ?? k.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}

export function statusTone(code: string | null | undefined): Tone {
  if (!code) return 'neutral'
  return MAP[code.toLowerCase().replace(/[\s-]+/g, '_')]?.[1] ?? 'neutral'
}

/** Mastery band (brief §1): attained ≥ threshold, near = within 15 points below, below that = not attained,
 *  no score = not enough evidence. Display only - the server's "attained" decision is never recomputed here. */
export type Band = 'attained' | 'near' | 'not_attained' | 'insufficient'
export const NEAR_BAND = 15

export function band(score: number | null | undefined, threshold: number, attained?: boolean | null): Band {
  if (score === null || score === undefined) return 'insufficient'
  if (attained === true || (attained !== false && score >= threshold)) return 'attained'
  return score >= threshold - NEAR_BAND ? 'near' : 'not_attained'
}
export const BAND_TONE: Record<Band, Tone> = { attained: 'good', near: 'near', not_attained: 'bad', insufficient: 'neutral' }
