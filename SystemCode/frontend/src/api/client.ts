import {
  parseModel,
  type Model,
  type Schemas,
  type UploadMetadata,
} from './contracts'
import { ApiError } from './errors'

export type Transport = (url: string, init: RequestInit) => Promise<Response>
export type ReplanningStatus = 'completed' | 'failed' | 'not_needed'
export type RequestOptions = { signal?: AbortSignal; timeoutMs?: number; onReplanning?: (status: ReplanningStatus | undefined) => void }
export type PageQuery = { limit?: number; offset?: number }
export type InspectionQuery = PageQuery & {
  status?: Model<'InspectionResponse'>['status'] | 'all'
}
export type TaskQuery = PageQuery & {
  status?: Model<'TaskRecord'>['status'] | 'all'
}
export type Operation<T> = Readonly<{ requestId: string; payload: Readonly<T> }>

// Keep this object for retries. A changed payload/version must start a new operation.
export function createOperation<T extends object>(payload: T): Operation<T> {
  return Object.freeze({
    requestId: crypto.randomUUID(),
    payload: Object.freeze(structuredClone(payload)),
  })
}

export function resolveImageUrl(
  value: string,
  origin = window.location.origin,
): string {
  const base = new URL(origin)
  const url = new URL(value, base)
  if (
    url.origin !== base.origin ||
    !/^\/api\/v1\/inspections\/[0-9a-f]{32}\/image$/.test(url.pathname) ||
    url.search ||
    url.hash
  ) {
    throw new ApiError(
      'contract_mismatch',
      'The image URL does not match the contract.',
      0,
      'contract',
    )
  }
  return url.href
}

export function createApiClient(
  transport: Transport = (url, init) => fetch(url, init),
  timeoutMs = 8000,
  auth?: { csrfToken: () => string | undefined; onUnauthorized: () => void },
) {
  async function request<K extends keyof Schemas>(
    path: string,
    schema: K,
    init: RequestInit = {},
    options: RequestOptions = {},
  ): Promise<Model<K>> {
    const controller = new AbortController()
    const method = init.method ?? 'GET'
    const write = method !== 'GET' && path !== '/demo/assessments' && path !== '/assistant/knowledge/search' && path !== '/assistant/query'
    let dispatched = false
    let timedOut = false
    const abort = () => controller.abort()
    if (options.signal?.aborted) controller.abort()
    options.signal?.addEventListener('abort', abort, { once: true })
    const timer = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, options.timeoutMs ?? timeoutMs)
    try {
      if (controller.signal.aborted)
        throw new DOMException('Aborted', 'AbortError')
      dispatched = true
      const headers = new Headers(init.headers)
      const csrf = auth?.csrfToken()
      if (method !== 'GET' && csrf) headers.set('X-CSRF-Token', csrf)
      const response = await transport(`/api/v1${path}`, {
        ...init,
        headers,
        credentials: 'same-origin',
        signal: controller.signal,
      })
      if (response.status === 401) auth?.onUnauthorized()
      let data: unknown
      try {
        data = await response.json()
      } catch (error) {
        if (controller.signal.aborted) throw error
        throw new ApiError(
          'invalid_response',
          'Invalid JSON',
          response.status,
          'contract',
          null,
          write,
        )
      }
      if (!response.ok) {
        const failure = parseModel('ErrorResponse', data)
        throw new ApiError(
          failure.code,
          failure.message,
          response.status,
          'http',
          failure.details,
          write && response.status >= 500,
        )
      }
      try {
        const parsed = parseModel(schema, data)
        const status = response.headers.get('X-RoadGuard-Replanning')
        options.onReplanning?.(status === 'completed' || status === 'failed' || status === 'not_needed' ? status : undefined)
        return parsed
      } catch (error) {
        if (error instanceof ApiError && write)
          throw new ApiError(
            error.code,
            error.message,
            response.status,
            error.kind,
            error.details,
            true,
          )
        throw error
      }
    } catch (error) {
      if (error instanceof ApiError) {
        if (write && error.kind === 'contract' && !error.outcomeUnknown)
          throw new ApiError(
            error.code,
            error.message,
            error.status,
            error.kind,
            error.details,
            true,
          )
        throw error
      }
      const code = timedOut
        ? 'request_timeout'
        : controller.signal.aborted
          ? 'request_cancelled'
          : 'network_error'
      throw new ApiError(
        code,
        code,
        0,
        timedOut
          ? 'timeout'
          : controller.signal.aborted
            ? 'cancelled'
            : 'network',
        null,
        write && dispatched,
      )
    } finally {
      clearTimeout(timer)
      options.signal?.removeEventListener('abort', abort)
    }
  }
  const json = (method: string, value: unknown): RequestInit => ({
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  })
  const id = (value: string) => encodeURIComponent(value)
  const query = (values: Record<string, string | number | undefined>) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(values))
      if (value !== undefined) params.set(key, String(value))
    return params.size ? `?${params}` : ''
  }
  return {
    session: (o?: RequestOptions) => request('/auth/session', 'SessionResponse', {}, o),
    login: (username: string, password: string, o?: RequestOptions) => request('/auth/login', 'SessionResponse', json('POST', { username, password }), o),
    logout: (o?: RequestOptions) => request('/auth/logout', 'LogoutResponse', json('POST', {}), o),
    crewWorkspace: (o?: RequestOptions) => request('/crew/workspace', 'CrewWorkspaceResponse', {}, o),
    changeRequests: (o?: RequestOptions) => request('/assistant/change-requests', 'ChangeList', {}, o),
    changeRequest: (value: string, o?: RequestOptions) => request(`/assistant/change-requests/${id(value)}`, 'ChangeRecord', {}, o),
    previewChange: (payload: Model<'ChangePreview'>, o?: RequestOptions) => request('/assistant/change-requests', 'ChangeRecord', json('POST', payload), o),
    confirmChange: (value: string, payload: Model<'ChangeConfirm'>, o?: RequestOptions) => request(`/assistant/change-requests/${id(value)}/confirm`, 'ChangeRecord', json('POST', payload), o),
    cancelChange: (value: string, payload: Model<'ChangeConfirm'>, o?: RequestOptions) => request(`/assistant/change-requests/${id(value)}/cancel`, 'ChangeRecord', json('POST', payload), o),
    replanChange: (value: string, payload: Model<'ChangeReplan'>, o?: RequestOptions) => request(`/assistant/change-requests/${id(value)}/replan`, 'ChangeRecord', json('POST', payload), o),
    taskChanges: (o?: RequestOptions) => request('/assistant/task-changes', 'TaskChangeList', {}, o),
    taskChange: (value: string, o?: RequestOptions) => request(`/assistant/task-changes/${id(value)}`, 'TaskChangeRecord', {}, o),
    previewTaskChange: (payload: Model<'TaskChangePreview'>, o?: RequestOptions) => request('/assistant/task-changes/preview', 'TaskChangeRecord', json('POST', payload), o),
    confirmTaskChange: (value: string, payload: Model<'ChangeConfirm'>, o?: RequestOptions) => request(`/assistant/task-changes/${id(value)}/confirm`, 'TaskChangeRecord', json('POST', payload), o),
    cancelTaskChange: (value: string, payload: Model<'ChangeConfirm'>, o?: RequestOptions) => request(`/assistant/task-changes/${id(value)}/cancel`, 'TaskChangeRecord', json('POST', payload), o),
    replanTaskChange: (value: string, payload: Model<'ChangeReplan'>, o?: RequestOptions) => request(`/assistant/task-changes/${id(value)}/replan`, 'TaskChangeRecord', json('POST', payload), o),
    assistantStatus: (o?: RequestOptions) => request('/assistant/status', 'AssistantStatus', {}, o),
    assistantQuery: (payload: Model<'AssistantQuery'>, o?: RequestOptions) => request('/assistant/query', 'AssistantAnswer', json('POST', payload), o),
    knowledgeSearch: (payload: Model<'KnowledgeSearchRequest'>, o?: RequestOptions) =>
      request('/assistant/knowledge/search', 'KnowledgeSearchResponse', json('POST', payload), o),
    health: (o?: RequestOptions) => request('/health', 'HealthResponse', {}, o),
    demoScenarios: (o?: RequestOptions) =>
      request('/demo/scenarios', 'DemoScenarioCatalogue', {}, o),
    demoAssessment: (scenario_id: string, o?: RequestOptions) =>
      request(
        '/demo/assessments',
        'DemoAssessmentResponse',
        json('POST', { scenario_id }),
        o,
      ),
    upload: (
      image: File,
      metadata: UploadMetadata,
      key: string,
      o?: RequestOptions,
    ) => {
      const body = new FormData()
      body.set('image', image)
      body.set('metadata', JSON.stringify(metadata))
      return request(
        '/inspections',
        'InspectionUploadResponse',
        { method: 'POST', headers: { 'Idempotency-Key': key }, body },
        o,
      )
    },
    inspections: (q: InspectionQuery = {}, o?: RequestOptions) =>
      request(`/inspections${query(q)}`, 'InspectionListResponse', {}, o),
    inspection: (value: string, o?: RequestOptions) =>
      request(`/inspections/${id(value)}`, 'InspectionResponse', {}, o),
    review: (
      value: string,
      op: Operation<Omit<Model<'ReviewRequest'>, 'request_id'>>,
      o?: RequestOptions,
    ) =>
      request(
        `/inspections/${id(value)}/review`,
        'InspectionMutationResponse',
        json('POST', { ...op.payload, request_id: op.requestId }),
        o,
      ),
    tasks: (q: TaskQuery = {}, o?: RequestOptions) =>
      request(`/tasks${query(q)}`, 'TaskList', {}, o),
    snapshot: (expected_revision?: number, o?: RequestOptions) =>
      request(
        `/tasks/snapshot${query({ expected_revision })}`,
        'TaskSnapshot',
        {},
        o,
      ),
    task: (value: string, o?: RequestOptions) =>
      request(`/tasks/${id(value)}`, 'TaskRecord', {}, o),
    updateTask: (
      value: string,
      op: Operation<Omit<Model<'TaskPatch'>, 'request_id'>>,
      o?: RequestOptions,
    ) =>
      request(
        `/tasks/${id(value)}`,
        'TaskMutation',
        json('PATCH', { ...op.payload, request_id: op.requestId }),
        o,
      ),
    crews: (o?: RequestOptions) => request('/crews', 'CrewList', {}, o),
    updateCrew: (
      value: string,
      op: Operation<Omit<Model<'CrewPatch'>, 'request_id'>>,
      o?: RequestOptions,
    ) =>
      request(
        `/crews/${id(value)}`,
        'CrewMutation',
        json('PATCH', { ...op.payload, request_id: op.requestId }),
        o,
      ),
    recalculate: (payload: Model<'RecalculateRequest'>, o?: RequestOptions) =>
      request(
        '/route-plans/recalculate',
        'RecalculationResult',
        json('POST', payload),
        o,
      ),
    latestPlan: (algorithm: 'ga' | 'greedy', o?: RequestOptions) =>
      request(`/route-plans/latest${query({ algorithm })}`, 'RoutePlan', {}, o),
    plan: (value: string, o?: RequestOptions) =>
      request(`/route-plans/${id(value)}`, 'RoutePlan', {}, o),
  }
}
export type ApiClient = ReturnType<typeof createApiClient>
