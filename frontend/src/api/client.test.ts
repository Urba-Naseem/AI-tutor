import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, setAccessToken } from './client'

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('api client token refresh', () => {
  afterEach(() => { vi.unstubAllGlobals(); setAccessToken(null) })

  it('sends ONE refresh when several requests get 401 at the same time', async () => {
    // the server rotates refresh tokens and signs the session out if the same one is used twice
    let refreshes = 0
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/auth/refresh') {
        refreshes += 1
        await new Promise((r) => setTimeout(r, 20))
        return json(200, { access_token: 'new-token' })
      }
      const auth = (init?.headers as Record<string, string> | undefined)?.Authorization
      return auth === 'Bearer new-token' ? json(200, { ok: url }) : json(401, { detail: 'expired' })
    }))
    setAccessToken('old-token')
    const [a, b, c] = await Promise.all([api('/one'), api('/two'), api('/three')])
    expect(refreshes).toBe(1)
    expect([a, b, c]).toEqual([{ ok: '/api/one' }, { ok: '/api/two' }, { ok: '/api/three' }])
  })

  it('reports 401 when the session really has ended', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (url === '/api/auth/refresh' ? json(401, { detail: 'Session revoked' }) : json(401, { detail: 'expired' }))))
    await expect(api('/curriculum/upload-progress/x')).rejects.toMatchObject({ status: 401 })
  })
})
