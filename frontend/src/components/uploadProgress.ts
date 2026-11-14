import { useEffect, useState } from 'react'
import { ApiError, api } from '../api/client'

/**
 * A curriculum upload runs on the server as a background job, so it keeps going while the admin uses other pages.
 * This browser remembers which upload it started (localStorage, a per-viewer convenience only - the server holds
 * the real state), the Curriculum page follows it, and a small bar on every other page shows how far it has got.
 */
export type UploadProgress = {
  stage: string; message: string; courses_total: number | null; courses_done: number; step: number | null; steps: number | null
  done: boolean; result: unknown | null; error: string | null
}
export type Stored = { id: string; name: string; startedAt: number }

const KEY = 'curriculum-upload'
const EVENT = 'curriculum-upload-change'

export function currentUpload(): Stored | null {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Stored) : null
  } catch { return null }
}
export function rememberUpload(id: string, name: string) {
  try { localStorage.setItem(KEY, JSON.stringify({ id, name, startedAt: Date.now() })) } catch { /* storage unavailable */ }
  window.dispatchEvent(new Event(EVENT))
}
export function forgetUpload() {
  try { localStorage.removeItem(KEY) } catch { /* storage unavailable */ }
  window.dispatchEvent(new Event(EVENT))
}

/** The upload this browser started, kept in sync across components and tabs. */
export function useStoredUpload(): Stored | null {
  const [s, setS] = useState<Stored | null>(currentUpload)
  useEffect(() => {
    const sync = () => setS(currentUpload())
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync)
    return () => { window.removeEventListener(EVENT, sync); window.removeEventListener('storage', sync) }
  }, [])
  return s
}

/** Polls the server every 1.5 s until the upload is done. `lost` = the server no longer knows it (e.g. it restarted);
 *  `signedOut` = this browser is no longer signed in (the upload keeps running; signing in again resumes the check). */
export function useUploadProgress(upload: Stored | null) {
  const [p, setP] = useState<UploadProgress | null>(null)
  const [lost, setLost] = useState(false)
  const [signedOut, setSignedOut] = useState(false)
  const id = upload?.id
  const startedAt = upload?.startedAt ?? 0
  useEffect(() => {
    setP(null)
    setLost(false)
    setSignedOut(false)
    if (!id) return
    let stop = false
    let timer: number | undefined
    const poll = async () => {
      let finished = false
      try {
        const r = await api<UploadProgress>(`/curriculum/upload-progress/${id}`)
        if (stop) return
        setP(r)
        finished = r.done
      } catch (e) {
        if (stop) return
        const status = e instanceof ApiError ? e.status : 0
        if (status === 401) { setSignedOut(true); finished = true } // stop asking; nothing to see until signed in
        else if (status === 404 && Date.now() - startedAt > 20000) { setLost(true); finished = true } // the server forgot it
        // anything else (network blip, server busy): keep checking
      }
      if (!finished && !stop) timer = window.setTimeout(poll, 1500)
    }
    poll()
    return () => { stop = true; window.clearTimeout(timer) }
  }, [id, startedAt])
  return { p, lost, signedOut }
}

export function elapsed(startedAt: number, now: number) {
  const s = Math.max(0, Math.round((now - startedAt) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** One line for the progress: "Found 19 courses … · 7 of 19 courses extracted". */
export function progressLine(p: UploadProgress | null) {
  if (!p) return 'Uploading the document'
  const parts = [p.message]
  if (p.courses_total && !p.steps && p.stage !== 'done') parts.push(`${p.courses_done} of ${p.courses_total} courses extracted`)
  return parts.join(' · ')
}
