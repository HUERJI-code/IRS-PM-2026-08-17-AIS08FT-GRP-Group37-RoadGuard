import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'

afterEach(() => vi.unstubAllGlobals())
it('switches explicitly between live, normal, empty and failed sources without network fallback', async () => {
  const network = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>().mockImplementation(async (url) => new Response(JSON.stringify(url.endsWith('/auth/session') ? { user: { user_id: 'c', username: 'c', display_name: 'C', role: 'dispatcher', crew_id: null }, csrf_token: 'test', expires_at: Math.floor(Date.now()/1000)+3600 } : { status: 'ok', database: 'ok', api_version: 'v1', input_revision: 5 })))
  vi.stubGlobal('fetch', network)
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  )
  await screen.findByText(/Application and database connected · Input revision 5/)
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Data source' }),
    'normal',
  )
  expect(await screen.findByText(/Mock connection status/)).toBeVisible()
  expect(screen.getByText(/Fixed read-only snapshot/)).toBeVisible()
  await user.click(screen.getByText('Check data connection'))
  await user.click(screen.getByRole('button', { name: 'Read current source' }))
  expect(await screen.findByText(/Active tasks: 1/)).toBeVisible()
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Data source' }),
    'empty',
  )
  expect(screen.queryByText(/Active tasks:1/)).not.toBeInTheDocument()
  await user.click(screen.getByText('Check data connection'))
  await user.click(screen.getByRole('button', { name: 'Read current source' }))
  expect(await screen.findByText('This list is empty.')).toBeVisible()
  expect(screen.getByText(/An empty task list differs from having no plan/)).toBeVisible()
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Data source' }),
    'failure',
  )
  await user.click(screen.getByText('Check data connection'))
  await user.click(screen.getByRole('button', { name: 'Read current source' }))
  expect(
    await within(screen.getByRole('region', { name: 'Data source' })).findByRole(
      'alert',
    ),
  ).toHaveTextContent('The database is temporarily unavailable')
  // The initial task read may start before the source switch; switching aborts it.
  const initialTasks = network.mock.calls.filter(([url]) => url.startsWith('/api/v1/tasks?'))
  for (const [, init] of initialTasks) expect(init?.signal?.aborted).toBe(true)
  expect(network.mock.calls.filter(([url]) => !url.startsWith('/api/v1/tasks?')).map(([url]) => url))
    .toEqual(['/api/v1/auth/session', '/api/v1/health'])
})
