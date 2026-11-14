import { useState, type InputHTMLAttributes } from 'react'

/** Password field with a labelled show/hide toggle (UI rules §6). Takes the same props as <input>. */
export default function PasswordInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { id: string }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="password-input">
      <input {...props} type={shown ? 'text' : 'password'} />
      <button type="button" className="secondary small" aria-pressed={shown} aria-controls={props.id} onClick={() => setShown(!shown)}>
        {shown ? 'Hide' : 'Show'}<span className="sr-only"> password</span>
      </button>
    </div>
  )
}
