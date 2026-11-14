/** Imperative API for the accessible dialog rendered by <DialogHost /> (see Dialog.tsx). */
export type DialogRequest = {
  title: string
  message: string
  confirmLabel: string
  danger?: boolean
  /** When set, the dialog asks for text with this visible label (required). */
  inputLabel?: string
  resolve: (value: string | null) => void
}

let open: ((r: DialogRequest) => void) | null = null

/** Called by DialogHost on mount/unmount. */
export function registerDialog(fn: ((r: DialogRequest) => void) | null) {
  open = fn
}

function request(r: Omit<DialogRequest, 'resolve'>): Promise<string | null> {
  return new Promise((resolve) => {
    if (!open) return resolve(null)
    open({ ...r, resolve })
  })
}

/** Ask the user to confirm an action. Say what will happen in `message`. Resolves true when confirmed. */
export async function askConfirm(o: { title: string; message: string; confirmLabel: string; danger?: boolean }) {
  return (await request(o)) !== null
}

/** Ask the user for a short required text (e.g. a reason). Resolves null when cancelled. */
export function askText(o: { title: string; message: string; inputLabel: string; confirmLabel: string; danger?: boolean }) {
  return request(o)
}
