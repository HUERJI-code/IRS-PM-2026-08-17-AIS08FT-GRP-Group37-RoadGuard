import fixtures from './fixtures.json'
import type { Transport } from '../client'

export type MockScenario = 'normal' | 'empty' | 'failure' | 'conflict'
export const mockFixtures = fixtures

export function createMockTransport(scenario: MockScenario): Transport {
  return async (url, init) => {
    if (init.signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    const reply = (value: unknown, status = 200) =>
      new Response(JSON.stringify(value), {
        status,
        headers: {
          'Content-Type': 'application/json',
          'X-RoadGuard-Mock': 'true',
        },
      })
    const failure = (code: string, status: number) =>
      reply(
        {
          code,
          message: 'Explicit synthetic fixture response.',
          details: null,
        },
        status,
      )
    if (scenario === 'failure') return failure('database_unavailable', 503)
    if (scenario === 'conflict') return failure('stale_input_revision', 409)
    // This transport has no fetch fallback, so mock mode cannot reach live writes.
    if ((init.method ?? 'GET') !== 'GET')
      return failure('mock_write_unavailable', 409)
    const parsed = new URL(url, 'http://mock.invalid')
    const path = parsed.pathname.replace(/^\/api\/v1/, '')
    const data: Record<string, unknown> = fixtures[scenario]
    if (
      path === '/tasks/snapshot' &&
      parsed.searchParams.has('expected_revision')
    ) {
      const snapshot = data[path] as { input_revision: number }
      if (
        Number(parsed.searchParams.get('expected_revision')) !==
        snapshot.input_revision
      )
        return failure('stale_input_revision', 409)
    }
    if (path === '/inspections' || path === '/tasks') {
      const source = structuredClone(data[path]) as {
        items: { status: string }[]
        total: number
        limit: number
        offset: number
      }
      const status =
        parsed.searchParams.get('status') ??
        (path === '/tasks' ? 'active' : 'all')
      const allowed =
        path === '/tasks'
          ? ['all', 'active', 'completed', 'cancelled']
          : ['all', 'no_detection', 'pending_review', 'accepted', 'rejected']
      const limit = Number(parsed.searchParams.get('limit') ?? 50)
      const offset = Number(parsed.searchParams.get('offset') ?? 0)
      if (
        !allowed.includes(status) ||
        !Number.isInteger(limit) ||
        limit < 1 ||
        limit > 100 ||
        !Number.isInteger(offset) ||
        offset < 0
      )
        return failure('validation_error', 422)
      source.items = source.items.filter(
        (item) => status === 'all' || item.status === status,
      )
      source.total = source.items.length
      source.items = source.items.slice(offset, offset + limit)
      source.limit = limit
      source.offset = offset
      return reply(source)
    }
    const key =
      path === '/route-plans/latest'
        ? `${path}?algorithm=${parsed.searchParams.get('algorithm')}`
        : path
    if (
      path === '/route-plans/latest' &&
      !['ga', 'greedy'].includes(parsed.searchParams.get('algorithm') ?? '')
    )
      return failure('validation_error', 422)
    if (!(key in data))
      return failure(
        path.startsWith('/route-plans/') ? 'route_plan_not_found' : 'not_found',
        404,
      )
    return reply(data[key])
  }
}
