/** Short confirmations ("Saved") shown by <ToastHost /> (DESIGN.md §5). Errors that need action are never toast-only. */
export type ToastItem = { id: number; message: string }

let listener: ((t: ToastItem) => void) | null = null
let seq = 0

export function registerToasts(fn: ((t: ToastItem) => void) | null) {
  listener = fn
}

export function toast(message: string) {
  listener?.({ id: ++seq, message })
}
