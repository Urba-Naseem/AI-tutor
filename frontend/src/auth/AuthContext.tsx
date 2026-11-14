import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, refreshAccessToken, setAccessToken } from '../api/client'

export type Role = 'student' | 'instructor' | 'admin' | 'exam_staff'
export type User = { id: number; email: string; full_name: string; role: Role; student_number?: string | null; program_code?: string | null }

type Ctx = {
  user: User | null
  ready: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthCtx = createContext<Ctx>(null as unknown as Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    // restore the session from the HttpOnly refresh cookie
    refreshAccessToken()
      .then(async (ok) => {
        if (ok) setUser(await api<User>('/auth/me'))
      })
      .finally(() => setReady(true))
  }, [])

  async function login(email: string, password: string) {
    const r = await api<{ access_token: string; user: User }>('/auth/login', { body: { email, password } })
    setAccessToken(r.access_token)
    setUser(r.user)
    return r.user
  }

  async function logout() {
    await api('/auth/logout', { method: 'POST' }).catch(() => undefined)
    setAccessToken(null)
    setUser(null)
  }

  return <AuthCtx.Provider value={{ user, ready, login, logout }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)
