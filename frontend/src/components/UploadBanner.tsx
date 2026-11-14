import { Upload } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { forgetUpload, progressLine, useStoredUpload, useUploadProgress, type Stored } from './uploadProgress'

/** Bar under the top bar while this browser's curriculum upload runs (see uploadProgress.ts). */
function Banner({ upload }: { upload: Stored }) {
  const { p, lost, signedOut } = useUploadProgress(upload)
  const text = signedOut ? `You were signed out. Sign in again to see how the upload of ${upload.name} is going (it keeps running).`
    : lost ? 'The curriculum upload was interrupted (the server restarted). Upload the file again.'
    : p?.done ? (p.error ? `The curriculum upload stopped: ${p.error}` : `The curriculum upload of ${upload.name} has finished.`)
      : `Uploading ${upload.name}: ${progressLine(p)}`
  return (
    <div className={`upload-banner${p?.error || lost ? ' is-error' : p?.done ? ' is-done' : ''}`} role="status" aria-live="polite">
      <Upload className="icon-inline" aria-hidden="true" />
      <span className="upload-banner-text">{text}</span>
      {lost ? <button type="button" className="ghost" onClick={forgetUpload}>Dismiss</button>
        : <Link to="/admin/curriculum">{p?.done ? 'See the result' : 'Open'}</Link>}
    </div>
  )
}

/** Shown on every page except Curriculum (which has the full progress panel) while this browser's upload runs. */
export function UploadBanner() {
  const upload = useStoredUpload()
  const { pathname } = useLocation()
  if (!upload || pathname.startsWith('/admin/curriculum')) return null
  return <Banner upload={upload} />
}
