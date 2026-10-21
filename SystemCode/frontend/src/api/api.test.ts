import knowledgeFixture from '../test/knowledge-fixture.json'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createApiClient,
  createOperation,
  resolveImageUrl,
  type Transport,
} from './client'
import { parseModel, type Schemas } from './contracts'
import { ApiError, errorMessage } from './errors'
import {
  formatMinutes,
  formatRuntime,
  formatSingaporeTime,
  stopTime,
} from './format'
import { createMockTransport, mockFixtures } from './mock/transport'

const reply = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status })
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('backend contract snapshots', () => {
  const schemaFor = (path: string): keyof Schemas => {
    if (path === '/health') return 'HealthResponse'
    if (path === '/inspections') return 'InspectionListResponse'
    if (path === '/tasks') return 'TaskList'
    if (path === '/tasks/snapshot') return 'TaskSnapshot'
    if (path === '/crews') return 'CrewList'
    if (path === '/demo/scenarios') return 'DemoScenarioCatalogue'
    if (path.startsWith('/route-plans/')) return 'RoutePlan'
    if (path.startsWith('/inspections/')) return 'InspectionResponse'
    return 'TaskRecord'
  }
  for (const [scenario, responses] of Object.entries(mockFixtures)) {
    it(`validates every ${scenario} response against the exported backend schema`, () => {
      for (const [path, value] of Object.entries(responses))
        expect(() => parseModel(schemaFor(path), value)).not.toThrow()
    })
  }
  it('rejects missing fields, extra fields and coerced numbers', () => {
    const health = mockFixtures.normal['/health']
    for (const invalid of [
      { status: 'ok' },
      { ...health, extra: true },
      { ...health, input_revision: '1' },
    ]) {
      expect(() => parseModel('HealthResponse', invalid)).toThrow(ApiError)
    }
  })
  it('keeps inspection provenance, one-box projection and null fields', async () => {
    const api = createApiClient(createMockTransport('normal'))
    const pending = await api.inspections({ status: 'pending_review' })
    expect(pending.total).toBe(1)
    expect(pending.items[0].detections).toHaveLength(1)
    expect(pending.items[0].task_id).toBeNull()
    const none = await api.inspections({ status: 'no_detection' })
    expect(none.items[0].detections).toHaveLength(0)
    const crews = await api.crews()
    expect(crews.crews).toHaveLength(4)
    const plan = await api.latestPlan('ga')
    expect(plan.crew_routes).toHaveLength(4)
    expect(plan.matrix_is_simulated).toBe(true)
  })
})

describe('requests and failures', () => {
  it('uses exactly image + metadata and leaves the multipart boundary to the browser', async () => {
    const transport = vi
      .fn<Transport>()
      .mockResolvedValue(
        reply(
          {
            inspection_id: 'a'.repeat(32),
            status: 'no_detection',
            detection: null,
            task_id: null,
          },
          201,
        ),
      )
    const api = createApiClient(transport)
    await api.upload(
      new File(['bytes'], 'road.png', { type: 'image/png' }),
      {
        mode: 'real',
        latitude: 1.34,
        longitude: 103.7,
        road_type: 'public_motor_road',
      },
      'upload_1',
    )
    const [url, request] = transport.mock.calls[0]
    expect(url).toBe('/api/v1/inspections')
    expect(new Headers(request.headers).get('Idempotency-Key')).toBe('upload_1')
    expect(new Headers(request.headers).has('Content-Type')).toBe(false)
    const form = request.body as FormData
    expect([...form.keys()]).toEqual(['image', 'metadata'])
    expect(JSON.parse(form.get('metadata') as string)).not.toHaveProperty(
      'scenario_id',
    )
  })
  it('freezes each operation and reuses its ID on an explicit retry', async () => {
    const transport = vi
      .fn<Transport>()
      .mockRejectedValue(new TypeError('offline'))
    const api = createApiClient(transport)
    const payload = { expected_version: 2, available: false }
    const operation = createOperation(payload)
    payload.available = true
    await expect(api.updateCrew('crew-01', operation)).rejects.toMatchObject({
      outcomeUnknown: true,
      kind: 'network',
    })
    expect(transport).toHaveBeenCalledTimes(1)
    await expect(api.updateCrew('crew-01', operation)).rejects.toBeInstanceOf(
      ApiError,
    )
    expect(transport.mock.calls[0][1].body).toBe(
      transport.mock.calls[1][1].body,
    )
    expect(JSON.parse(transport.mock.calls[0][1].body as string)).toEqual({
      request_id: operation.requestId,
      expected_version: 2,
      available: false,
    })
    expect(createOperation(payload).requestId).not.toBe(operation.requestId)
  })
  it('never retries recalculation automatically or invents an idempotency key', async () => {
    const transport = vi
      .fn<Transport>()
      .mockRejectedValue(new TypeError('offline'))
    await expect(
      createApiClient(transport).recalculate({ expected_revision: 4 }),
    ).rejects.toMatchObject({ outcomeUnknown: true })
    expect(transport).toHaveBeenCalledTimes(1)
    expect(JSON.parse(transport.mock.calls[0][1].body as string)).toEqual({
      expected_revision: 4,
    })
  })
  it('preserves structured errors and does not branch on human messages', async () => {
    const transport = vi
      .fn<Transport>()
      .mockResolvedValue(
        reply(
          {
            code: 'stale_record_version',
            message: 'arbitrary words',
            details: { current_version: 3 },
          },
          409,
        ),
      )
    const error = await createApiClient(transport)
      .health()
      .catch((error) => error)
    expect(error).toMatchObject({
      status: 409,
      code: 'stale_record_version',
      details: { current_version: 3 },
    })
    expect(errorMessage(error)).toContain('Refresh')
  })
  it('detects HTML fallback and invalid success bodies', async () => {
    const transport = vi
      .fn<Transport>()
      .mockResolvedValueOnce(new Response('<html>'))
      .mockResolvedValueOnce(reply({ status: 'ok' }))
    const api = createApiClient(transport)
    await expect(api.health()).rejects.toMatchObject({
      code: 'invalid_response',
    })
    await expect(api.health()).rejects.toMatchObject({
      code: 'contract_mismatch',
    })
  })
  it('aborts a timeout without issuing another request', async () => {
    vi.useFakeTimers()
    const transport = vi.fn<Transport>().mockImplementation(
      (_url, init) =>
        new Promise((_, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        }),
    )
    const result = createApiClient(transport, 25)
      .health()
      .catch((error) => error)
    await vi.advanceTimersByTimeAsync(25)
    expect(await result).toMatchObject({ kind: 'timeout' })
    expect(transport).toHaveBeenCalledTimes(1)
  })
  it('does not dispatch when the caller already cancelled', async () => {
    const transport = vi.fn<Transport>()
    const controller = new AbortController()
    controller.abort()
    await expect(
      createApiClient(transport).health({ signal: controller.signal }),
    ).rejects.toMatchObject({ kind: 'cancelled' })
    expect(transport).not.toHaveBeenCalled()
  })
  it('only accepts same-origin inspection images', () => {
    const path = `/api/v1/inspections/${'a'.repeat(32)}/image`
    expect(resolveImageUrl(path, 'http://localhost:5173')).toBe(
      'http://localhost:5173' + path,
    )
    for (const value of [
      'javascript:alert(1)',
      'https://other.example' + path,
      '/wrong',
      path + '?secret=x',
    ])
      expect(() => resolveImageUrl(value, 'http://localhost:5173')).toThrow()
  })
})

describe('explicit mock source', () => {
  it('supports pagination, filtering, empty lists and absent plans without touching fetch', async () => {
    const network = vi.fn()
    vi.stubGlobal('fetch', network)
    const normal = createApiClient(createMockTransport('normal'))
    expect(
      (await normal.inspections({ limit: 1, offset: 1 })).items,
    ).toHaveLength(1)
    expect((await normal.inspections({ offset: 99 })).items).toHaveLength(0)
    const empty = createApiClient(createMockTransport('empty'))
    expect((await empty.tasks()).items).toEqual([])
    await expect(empty.latestPlan('ga')).rejects.toMatchObject({
      code: 'route_plan_not_found',
      status: 404,
    })
    await expect(
      normal.updateCrew(
        'crew-01',
        createOperation({ expected_version: 1, available: false }),
      ),
    ).rejects.toMatchObject({ code: 'mock_write_unavailable' })
    expect(network).not.toHaveBeenCalled()
  })
  it('has deterministic service failure and stale-version scenarios', async () => {
    await expect(
      createApiClient(createMockTransport('failure')).tasks(),
    ).rejects.toMatchObject({ status: 503 })
    await expect(
      createApiClient(createMockTransport('conflict')).snapshot(),
    ).rejects.toMatchObject({ code: 'stale_input_revision' })
    await expect(
      createApiClient(createMockTransport('normal')).snapshot(9999),
    ).rejects.toMatchObject({ code: 'stale_input_revision' })
  })
})

describe('units and Singapore time', () => {
  it('distinguishes missing values from zero and milliseconds from minutes', () => {
    expect(formatMinutes(null)).toBe('Not provided')
    expect(formatMinutes(0)).toBe('0 min')
    expect(formatRuntime(0)).toBe('0 ms')
    expect(formatRuntime(1200)).toBe('1,200 ms')
  })
  it('converts UTC and stop offsets to Singapore time, including date rollover', () => {
    expect(formatSingaporeTime('2026-10-15T01:00:00Z')).toContain('09:00')
    expect(stopTime('2026-10-15T15:30:00Z', 60)).toContain('16')
    expect(stopTime('2026-10-15T15:30:00Z', 60)).toContain('00:30')
    expect(stopTime('2026-10-15T01:00:00Z', null)).toBe('Not provided')
    expect(formatSingaporeTime('2026-10-15T01:00:00')).toBe('Invalid time')
  })
})

describe('endpoint adapters', () => {
  it('routes all remaining read and mutation methods with current version fields', async () => {
    const transport = vi
      .fn<Transport>()
      .mockImplementation(async () =>
        reply(
          { code: 'validation_error', message: 'fixture', details: null },
          422,
        ),
      )
    const api = createApiClient(transport)
    const review = createOperation({
      expected_version: 1,
      action: 'confirm' as const,
      detection_id: 'det-1',
    })
    const task = createOperation({
      expected_version: 3,
      status: 'completed' as const,
    })
    const calls: [string, string, () => Promise<unknown>][] = [
      ['GET', '/api/v1/demo/scenarios', () => api.demoScenarios()],
      [
        'POST',
        '/api/v1/demo/assessments',
        () => api.demoAssessment('high_confidence'),
      ],
      ['GET', '/api/v1/inspections/abc', () => api.inspection('abc')],
      [
        'POST',
        '/api/v1/inspections/abc/review',
        () => api.review('abc', review),
      ],
      ['GET', '/api/v1/tasks/abc', () => api.task('abc')],
      ['PATCH', '/api/v1/tasks/abc', () => api.updateTask('abc', task)],
      ['GET', '/api/v1/route-plans/plan-abc', () => api.plan('plan-abc')],
    ]
    for (const [method, url, call] of calls) {
      await expect(call()).rejects.toMatchObject({ status: 422 })
      const [actual, init] = transport.mock.calls.at(-1)!
      expect(actual).toBe(url)
      expect(init.method ?? 'GET').toBe(method)
    }
    expect(JSON.parse(transport.mock.calls[3][1].body as string)).toEqual({
      ...review.payload,
      request_id: review.requestId,
    })
    expect(JSON.parse(transport.mock.calls[5][1].body as string)).toEqual({
      ...task.payload,
      request_id: task.requestId,
    })
  })
  it('marks malformed mutation responses as uncertain outcomes', async () => {
    const api = createApiClient(async () => reply({ broken: true }, 500))
    await expect(
      api.updateCrew(
        'crew-01',
        createOperation({ expected_version: 1, available: false }),
      ),
    ).rejects.toMatchObject({ outcomeUnknown: true, kind: 'contract' })
  })
})


it('retrieves static evidence with the existing cookie and CSRF client', async () => {
  const transport = vi.fn<Transport>().mockResolvedValue(reply(knowledgeFixture))
  const api = createApiClient(transport, 8000, { csrfToken: () => 'test-csrf', onUnauthorized: vi.fn() })
  const result = await api.knowledgeSearch({ query: 'crew account', limit: 2, rule_version: 'demo-rules-v2' })
  expect(result.answer_generated).toBe(false)
  expect(result.hits[0].citation_id).toContain('#')
  const [url, init] = transport.mock.calls[0]
  expect(url).toBe('/api/v1/assistant/knowledge/search')
  expect(init.credentials).toBe('same-origin')
  expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('test-csrf')
  expect(JSON.parse(init.body as string).rule_version).toBe('demo-rules-v2')
})

it('does not label a failed read-only search as an uncertain business write', async () => {
  const transport = vi.fn<Transport>().mockRejectedValue(new TypeError('offline'))
  await expect(createApiClient(transport).knowledgeSearch({ query: 'repair rules', limit: 5 })).rejects.toMatchObject({ outcomeUnknown: false })
  expect(transport).toHaveBeenCalledTimes(1)
})
