/** Frame for sign in / register / verify / reset: just the centred form card, no side panel. */
import type { ReactNode } from 'react'

export function AuthShell({ children, wide }: { children: ReactNode; wide?: 'medium' | 'wide' }) {
  return <main className={`auth-page${wide ? ` auth-${wide}` : ''}`}>{children}</main>
}
