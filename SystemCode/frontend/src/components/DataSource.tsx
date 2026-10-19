import { useEffect, useRef, useState } from 'react'
import { useApi, type DataMode } from '../api/context'
import { ApiError } from '../api/errors'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NoPlanState,
} from './RequestState'

export default function DataSource() {
  const { mode, setMode, api } = useApi()
  const [state, setState] = useState<
    | { kind: 'idle' | 'loading' | 'ready'; total?: number; plan?: string }
    | { kind: 'error'; error: unknown }
  >({ kind: 'idle' })
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])
  async function inspect() {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setState({ kind: 'loading' })
    try {
      const snapshot = await api.snapshot(undefined, {
        signal: controller.signal,
      })
      let plan: string | undefined
      try {
        plan = (await api.latestPlan('ga', { signal: controller.signal }))
          .plan_id
      } catch (error) {
        if (
          !(error instanceof ApiError) ||
          error.code !== 'route_plan_not_found'
        )
          throw error
      }
      if (controller.signal.aborted) return
      setState({ kind: 'ready', total: snapshot.total, plan })
    } catch (error) {
      if (!controller.signal.aborted) setState({ kind: 'error', error })
    }
  }
  return (
    <section className={`data-source ${mode !== 'live' ? 'mock-source' : ''}`} aria-label="Data source">
      <div className="source-selector">
      <label htmlFor="data-mode">Data source</label>
      <select
        id="data-mode"
        value={mode}
        onChange={(event) => setMode(event.target.value as DataMode)}
      >
        <option value="live">Live backend API</option>
        <option value="normal">Mock · Normal example</option>
        <option value="empty">Mock · Empty data</option>
        <option value="failure">Mock · Service failure</option>
        <option value="conflict">Mock · Revision conflict</option>
      </select>
      </div>
      {mode !== 'live' && <p className="source-warning">Mock data · Fixed read-only snapshot, not operational data. Changes are blocked and are not sent to the backend.</p>}
      <details>
        <summary>Check data connection</summary>
        <div className="diagnostic-panel">
        <p>Read the selected source. Service failures never switch automatically to mock data.</p>
        <p>Read-only check of active task count and GA plan availability; does not create or recalculate plans.</p>
        <button
          className="text-button"
          disabled={state.kind === 'loading'}
          onClick={() => void inspect()}
        >
          Read current source
        </button>
        {state.kind === 'loading' && <LoadingState />}
        {state.kind === 'error' && <ErrorState error={state.error} />}
        {state.kind === 'ready' && (
          <>
            {state.total === 0 ? (
              <EmptyState />
            ) : (
              <p role="status">Active tasks: {state.total}</p>
            )}
            {state.plan ? <p>Plan:{state.plan}</p> : <NoPlanState />}
          </>
        )}
        </div>
      </details>
    </section>
  )
}
