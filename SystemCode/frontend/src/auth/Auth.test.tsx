import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../App'
import type { Model } from '../api/contracts'
import { createMockTransport } from '../api/mock/transport'
import planning from '../test/planning-fixtures.json'

let current: Model<'SessionResponse'> | null
let failLogout: boolean
let network: ReturnType<typeof vi.fn<typeof fetch>>
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
function account(role: Model<'Account'>['role']): Model<'SessionResponse'> {
  return { user: { user_id: role, username: role, display_name: role, role, crew_id: role === 'crew' ? 'crew-02' : null }, csrf_token: 'csrf-' + role, expires_at: Math.floor(Date.now()/1000)+3600 }
}
beforeEach(() => {
  current = null; failLogout = false
  const mock = createMockTransport('normal')
  network = vi.fn<typeof fetch>().mockImplementation(async (input, init = {}) => {
    const url=String(input)
    if (url.endsWith('/auth/session')) return current ? reply(current) : reply({ code: 'authentication_required', message: 'Sign in' },401)
    if (url.endsWith('/auth/login')) {
      const body=JSON.parse(init.body as string)
      if (body.password !== 'test-password') return reply({ code: 'invalid_credentials', message: 'Invalid credentials' },401)
      current=account(body.username); return reply(current)
    }
    if (url.endsWith('/auth/logout')) {
      if (failLogout) throw new TypeError('offline')
      current=null; return reply({ logged_out: true })
    }
    if (url.endsWith('/crew/workspace')) return reply({ crew: planning.crews.crews[1], plan: null, tasks: [], input_revision: 1 })
    return mock(url,init)
  })
  vi.stubGlobal('fetch',network)
})
afterEach(() => vi.unstubAllGlobals())
function open(path: string) { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>) }
async function signIn(role: string) {
  await screen.findByRole('heading',{name:'Sign in to workspace'})
  await userEvent.type(screen.getByLabelText('Username'), role)
  await userEvent.type(screen.getByLabelText('Password'), 'test-password')
  await userEvent.click(screen.getByRole('button',{name:'Sign in →'}))
}

it('keeps business pages hidden until an account signs in, then opens only inspector upload', async () => {
  open('/routes')
  await screen.findByRole('heading',{name:'Sign in to workspace'})
  expect(network.mock.calls.map(([url])=>url)).toEqual(['/api/v1/auth/session'])
  await signIn('inspector')
  await screen.findByRole('heading',{name:'Upload and results',level:1})
  expect(within(screen.getByRole('navigation')).getAllByRole('link')).toHaveLength(1)
  expect(screen.queryByRole('link',{name:/Four-crew routes|Manual review|Crew workspace/})).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Data source')).not.toBeInTheDocument()
  expect(network.mock.calls.some(([url])=>String(url).includes('/route-plans'))).toBe(false)
})

it('binds the crew account to crew-02 despite a different URL and denies dispatcher navigation', async () => {
  current=account('crew'); open('/crew?crew=crew-01')
  await screen.findByRole('heading',{name:'No route assigned yet'})
  expect(screen.getByText(/Crew · crew-02/)).toBeVisible()
  expect(within(screen.getByRole('navigation')).getAllByRole('link')).toHaveLength(1)
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(network.mock.calls.some(([url])=>String(url).endsWith('/crews'))).toBe(false)
})

it.each(['/inspections/new','/crew'])('redirects dispatcher away from %s without reading its business API', async (path) => {
  current=account('dispatcher');open(path)
  await screen.findByRole('heading',{name:'Task workspace',level:1})
  expect(within(screen.getByRole('navigation')).getAllByRole('link')).toHaveLength(5)
  expect(screen.queryByRole('link',{name:/Upload inspection|Crew workspace/})).not.toBeInTheDocument()
  expect(network.mock.calls.some(([url])=>String(url).endsWith('/crew/workspace') || String(url).endsWith('/demo/scenarios'))).toBe(false)
})

it('rejects incorrect login without business reads and can retry', async () => {
  open('/')
  await screen.findByLabelText('Username')
  await userEvent.type(screen.getByLabelText('Username'),'crew')
  await userEvent.type(screen.getByLabelText('Password'),'incorrect')
  await userEvent.click(screen.getByRole('button',{name:'Sign in →'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password')
  expect(screen.getByLabelText('Password')).toHaveValue('')
  await userEvent.type(screen.getByLabelText('Password'),'test-password')
  await userEvent.click(screen.getByRole('button',{name:'Sign in →'}))
  await screen.findByRole('heading',{name:'Crew workspace',level:1})
})

it('sends CSRF on logout, retains state after failure, and clears previous role on account change', async () => {
  current=account('crew');open('/crew')
  await screen.findByRole('heading',{name:'Crew workspace',level:1})
  failLogout=true
  await userEvent.click(screen.getByRole('button',{name:'Sign out'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('Sign-out failed')
  failLogout=false
  await userEvent.click(screen.getByRole('button',{name:'Sign out'}))
  await screen.findByRole('heading',{name:'Sign in to workspace'})
  const call=network.mock.calls.find(([url])=>String(url).endsWith('/auth/logout'))!
  expect(new Headers(call[1]?.headers).get('X-CSRF-Token')).toBe('csrf-crew')
  expect(call[1]?.credentials).toBe('same-origin')
  await signIn('inspector')
  await screen.findByRole('heading',{name:'Upload and results',level:1})
  expect(screen.queryByRole('heading',{name:'Crew workspace',level:1})).not.toBeInTheDocument()
})

it('revalidates role when another tab changes account', async () => {
  current=account('crew');open('/crew')
  await screen.findByRole('heading',{name:'Crew workspace',level:1})
  current=account('inspector')
  fireEvent(window,new StorageEvent('storage',{key:'roadguard-auth-change',newValue:'changed'}))
  await waitFor(()=>expect(screen.queryByRole('heading',{name:'Crew workspace',level:1})).not.toBeInTheDocument())
  await screen.findByRole('heading',{name:'Upload and results',level:1})
})
