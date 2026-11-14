import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { registerDialog, type DialogRequest } from './dialogApi'

/**
 * Accessible replacement for window.confirm / window.prompt (CLAUDE.md §1 dialogs, §4 destructive actions).
 * Uses the native <dialog> in modal mode: focus is trapped, Escape cancels, and focus returns to the
 * control that opened it. Mount <DialogHost /> once; call askConfirm / askText (dialogApi.ts) from handlers.
 */
export function DialogHost() {
  const [req, setReq] = useState<DialogRequest | null>(null)
  const [text, setText] = useState('')
  const ref = useRef<HTMLDialogElement>(null)
  const opener = useRef<HTMLElement | null>(null)
  const id = useId().replace(/:/g, '')

  useEffect(() => {
    registerDialog((r) => {
      opener.current = document.activeElement as HTMLElement | null
      setText('')
      setReq(r)
    })
    return () => registerDialog(null)
  }, [])

  useEffect(() => {
    const d = ref.current
    if (req && d && !d.open) {
      if (typeof d.showModal === 'function') d.showModal()
      else d.setAttribute('open', '')
    }
  }, [req])

  function finish(value: string | null) {
    req?.resolve(value)
    setReq(null)
    const d = ref.current
    if (d?.open) { if (typeof d.close === 'function') d.close(); else d.removeAttribute('open') }
    opener.current?.focus?.()
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (req?.inputLabel && !text.trim()) return
    finish(req?.inputLabel ? text.trim() : '')
  }

  return (
    <dialog ref={ref} className="dialog" aria-labelledby={`${id}-t`} aria-describedby={`${id}-m`} onCancel={(e) => { e.preventDefault(); finish(null) }}>
      {req && (
        <form onSubmit={submit}>
          <h2 id={`${id}-t`} className="mt-0">{req.title}</h2>
          <p id={`${id}-m`}>{req.message}</p>
          {req.inputLabel && (
            <div className="field">
              <label htmlFor={`${id}-i`}>{req.inputLabel}</label>
              <textarea id={`${id}-i`} value={text} onChange={(e) => setText(e.target.value)} required autoFocus />
            </div>
          )}
          <div className="row dialog-actions">
            <button type="button" className="secondary" onClick={() => finish(null)} autoFocus={!req.inputLabel}>Cancel</button>
            <button type="submit" className={req.danger ? 'danger' : undefined} disabled={!!req.inputLabel && !text.trim()}>{req.confirmLabel}</button>
          </div>
        </form>
      )}
    </dialog>
  )
}
