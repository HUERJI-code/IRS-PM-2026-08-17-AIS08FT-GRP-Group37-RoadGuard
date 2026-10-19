import { useEffect, useState } from 'react'

import { createApiClient } from '../api/client'
import { ApiContext } from '../api/context'
import { useContext } from 'react'
import type { Model } from '../api/contracts'
import { errorMessage } from '../api/errors'

type State =
  | { kind: 'loading' }
  | { kind: 'ready'; health: Model<'HealthResponse'> }
  | { kind: 'error'; error: unknown }
const fallbackApi = createApiClient()

export default function HealthStatus() {
  const context = useContext(ApiContext)
  const api = context?.api ?? fallbackApi
  const mock = context && context.mode !== 'live'
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    async function check() {
      try {
        const health = await api.health({ signal: controller.signal })
        if (active) setState({ kind: 'ready', health })
      } catch (error) {
        if (active) setState({ kind: 'error', error })
      }
    }
    void check()
    return () => {
      active = false
      controller.abort()
    }
  }, [attempt, api])

  return (
    <section className={`connection connection-${state.kind}`} aria-label="Service connection">
      <div role="status" aria-live="polite">
        <span className={`status-dot ${state.kind}`} aria-hidden="true" />
        {state.kind === 'loading' && 'Checking service…'}
        {state.kind === 'ready' &&
          `${mock ? 'Mock connection status' : 'Application and database connected'} · Input revision ${state.health.input_revision}`}
        {state.kind === 'error' && (
          <>
            Cannot connect to the service, or the response does not match the contract:{errorMessage(state.error)}
          </>
        )}
      </div>
      <details className="connection-details"><summary>Connection details</summary><p>
        This status is a snapshot of the latest check. It does not establish model, routing or assistant readiness. Check again after business changes.
      </p></details>
      <button
        className="text-button"
        disabled={state.kind === 'loading'}
        onClick={() => {
          setState({ kind: 'loading' })
          setAttempt((value) => value + 1)
        }}
      >
        Check connection again
      </button>
    </section>
  )
}
