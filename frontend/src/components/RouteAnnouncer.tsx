import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'

const APP = 'AI Tutor'

/**
 * Gives every page a unique <title> taken from its <h1> (WCAG 2.4.2) and, on client-side
 * navigation, announces the new page to screen readers and moves focus to the main content.
 * Pages need no changes: the title follows the h1, including h1s that fill in after data loads.
 */
export default function RouteAnnouncer() {
  const { pathname } = useLocation()
  const [message, setMessage] = useState('')
  const first = useRef(true)

  useEffect(() => {
    const sync = () => {
      const h1 = document.querySelector('h1')?.textContent?.trim()
      const title = h1 ? `${h1} · ${APP}` : APP
      if (document.title !== title) document.title = title
      return h1
    }
    const observer = new MutationObserver(sync)
    observer.observe(document.body, { childList: true, subtree: true, characterData: true })
    const t = window.setTimeout(() => {
      const h1 = sync()
      if (first.current) { first.current = false; return }
      setMessage(h1 ? `${h1} page` : 'Page loaded')
      document.getElementById('main')?.focus({ preventScroll: true })
    }, 50)
    return () => { observer.disconnect(); window.clearTimeout(t) }
  }, [pathname])

  return <p className="sr-only" role="status" aria-live="polite">{message}</p>
}
