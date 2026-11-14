import { CheckCircle2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { registerToasts, type ToastItem } from './toast'

const HIDE_AFTER_MS = 5000

/** One toast: auto-hides after ~5s; hovering or focusing it pauses the timer. */
function Toast({ item, onClose }: { item: ToastItem; onClose: () => void }) {
  const [paused, setPaused] = useState(false)
  const left = useRef(HIDE_AFTER_MS)
  const started = useRef(0)
  useEffect(() => {
    if (paused) return
    started.current = Date.now()
    const t = window.setTimeout(onClose, left.current)
    return () => { window.clearTimeout(t); left.current -= Date.now() - started.current }
  }, [paused, onClose])
  return (
    <div className="toast" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      <CheckCircle2 className="icon" aria-hidden="true" />
      <span>{item.message}</span>
      <button type="button" className="icon-btn" onClick={onClose} aria-label="Dismiss message" title="Dismiss">
        <X className="icon" aria-hidden="true" />
      </button>
    </div>
  )
}

/** Mount once. The live region is always present so screen readers announce new toasts politely. */
export default function ToastHost({ aboveBottomNav }: { aboveBottomNav?: boolean }) {
  const [items, setItems] = useState<ToastItem[]>([])
  useEffect(() => {
    registerToasts((t) => setItems((xs) => [...xs.slice(-2), t]))
    return () => registerToasts(null)
  }, [])
  return (
    <div className={`toasts${aboveBottomNav ? ' above-bottom-nav' : ''}`} role="status" aria-live="polite">
      {items.map((t) => <Toast key={t.id} item={t} onClose={() => setItems((xs) => xs.filter((x) => x.id !== t.id))} />)}
    </div>
  )
}
