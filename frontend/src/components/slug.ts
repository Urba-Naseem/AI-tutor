import { isValidElement, type ReactNode } from 'react'

/** Stable heading ids for the lesson outline ("On this page"). */
export function slugify(text: string) {
  return 'h-' + text.toLowerCase().replace(/[*_`$~[\]()]/g, '').trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

/** Plain text of rendered React children (used to derive the same slug from rendered headings). */
export function textOf(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children)
  return ''
}

/** h2/h3 headings of a Markdown document, skipping fenced code blocks. */
export function outlineOf(md: string) {
  const out: { level: 2 | 3; text: string; id: string }[] = []
  let fenced = false
  for (const line of md.split('\n')) {
    if (/^\s*```/.test(line)) { fenced = !fenced; continue }
    const m = !fenced && line.match(/^(#{2,3})\s+(.+?)\s*#*\s*$/)
    if (m) {
      const text = m[2].replace(/[*_`]/g, '')
      out.push({ level: m[1].length as 2 | 3, text, id: slugify(text) })
    }
  }
  return out
}
