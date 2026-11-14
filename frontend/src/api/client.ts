// Small fetch wrapper: adds the bearer token, refreshes it once on 401,
// and turns API error bodies into readable messages.

let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

function describe(detail: unknown): string {
  if (!detail) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail))
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`)
      .join('; ')
  if (typeof detail === 'object' && detail !== null && 'message' in detail)
    return String((detail as { message: unknown }).message)
  return JSON.stringify(detail)
}

// One refresh at a time: the server rotates the refresh token on every use and treats a second use of the same
// token as theft (it then signs the whole session out). When several requests hit 401 together - e.g. the upload
// progress check and a page load - they all wait for the same refresh instead of each sending their own.
let refreshing: Promise<boolean> | null = null

export function refreshAccessToken(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
        if (!res.ok) {
          accessToken = null
          return false
        }
        const data = await res.json()
        accessToken = data.access_token
        return true
      } catch {
        return false
      } finally {
        refreshing = null
      }
    })()
  }
  return refreshing
}

type Options = { method?: string; body?: unknown; form?: FormData; raw?: boolean }

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const send = () => {
    const headers: Record<string, string> = {}
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`
    let body: BodyInit | undefined
    if (opts.form) body = opts.form
    else if (opts.body !== undefined) {
      headers['Content-Type'] = 'application/json'
      body = JSON.stringify(opts.body)
    }
    return fetch('/api' + path, {
      method: opts.method ?? (body ? 'POST' : 'GET'),
      headers,
      body,
      credentials: 'include',
    })
  }
  let res = await send()
  if (res.status === 401 && !path.startsWith('/auth/') && (await refreshAccessToken())) res = await send()
  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      detail = (await res.json()).detail
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, describe(detail), detail)
  }
  if (opts.raw) return res as unknown as T
  if (res.status === 204) return undefined as T
  return res.json()
}

export async function download(path: string, filename: string) {
  const res = await api<Response>(path, { raw: true })
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
