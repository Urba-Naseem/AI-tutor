import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, setAccessToken } from '../api/client'
import { Alert, Badge, Bar } from '../components/ui'
import Markdown from '../components/Markdown'
import { routes } from '../routes'
import { ReadinessTable } from '../pages/student/DiagnosticPage'
import { PathSteps, type Path } from '../pages/student/PathPage'

afterEach(() => vi.restoreAllMocks())

describe('UI building blocks', () => {
  it('colours status badges by meaning', () => {
    render(<><Badge value="approved" /><Badge value="not_ready" /></>)
    expect(screen.getByText('Approved')).toHaveClass('ok')
    expect(screen.getByText('Not ready')).toHaveClass('bad')
  })

  it('exposes progress bars to assistive technology and clamps values', () => {
    render(<Bar value={140} threshold={60} />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '100')
    expect(bar).toHaveClass('ok')
  })

  it('announces errors as alerts', () => {
    render(<Alert>Something failed</Alert>)
    expect(screen.getByRole('alert')).toHaveTextContent('Something failed')
  })

  it('renders maths with KaTeX and code blocks', () => {
    const { container } = render(<Markdown>{'Area $a^2$\n\n```python\nprint(1)\n```'}</Markdown>)
    expect(container.querySelector('.katex')).not.toBeNull()
    expect(container.querySelector('pre code')).toHaveTextContent('print(1)')
  })
})

describe('role-based navigation (US-11.1)', () => {
  it('only admins see administration pages; students see learning pages', () => {
    const forRole = (role: string) => routes.filter((r) => r.nav && r.roles.includes(role as never)).map((r) => r.path)
    expect(forRole('admin')).toContain('/admin/users')
    expect(forRole('student')).not.toContain('/admin/users')
    expect(forRole('student')).toContain('/learn')
    expect(forRole('instructor')).toContain('/console')
    expect(forRole('exam_staff')).toContain('/audit')
  })
})

describe('API client', () => {
  it('sends the bearer token and turns error bodies into readable messages', async () => {
    setAccessToken('abc')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Nope' }), { status: 403 }))
    await expect(api('/users')).rejects.toThrow(ApiError)
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toMatchObject({ Authorization: 'Bearer abc' })
  })
})

describe('learner views', () => {
  it('shows per-CLO readiness (US-4.1)', () => {
    render(<ReadinessTable results={[{ clo_id: 1, clo_code: 'CLO1', description: 'Variables', score_pct: 100, level: 'ready', answered: 3, correct: 3 }]} />)
    expect(screen.getByText('CLO1')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('explains every path step (US-4.3)', () => {
    const path = {
      id: 1, version_no: 1, trigger: 'diagnostic', reason: null, summary: '', locked: false, lock_reason: null, covers_all_clos: true,
      progress: { done: 0, total: 1 }, next_step_id: 9, created_at: '',
      steps: [{ id: 9, position: 1, unit_id: 1, unit_number: 1, unit_title: 'Basics', clo_id: 1, clo_code: 'CLO1', clo_description: 'Variables', step_type: 'learn', label: 'Study', status: 'pending', rationale: 'Your diagnostic score was 40%.', rule: 'R-DEVELOPING', meta: {} }],
    } as Path
    render(<MemoryRouter><PathSteps path={path} courseId="1" staff /></MemoryRouter>)
    expect(screen.getByText(/Your diagnostic score was 40%/)).toBeInTheDocument()
    expect(screen.getByText('Up next')).toBeInTheDocument()
  })
})
