// Pages reachable without signing in (besides login / password reset).
import type { ReactElement } from 'react'
import { RegisterPage, VerifyEmailPage } from './pages/auth/RegisterPage'

export const publicRoutes: { path: string; element: ReactElement }[] = [
  { path: '/register', element: <RegisterPage /> },
  { path: '/verify-email', element: <VerifyEmailPage /> },
]
