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
    <section className={`connection connection-${state.kind}`} aria-label="服务连接">
      <div role="status" aria-live="polite">
        <span className={`status-dot ${state.kind}`} aria-hidden="true" />
        {state.kind === 'loading' && '正在检查服务…'}
        {state.kind === 'ready' &&
          `${mock ? '模拟连接状态' : '应用与数据库已连接'} · 输入版本 ${state.health.input_revision}`}
        {state.kind === 'error' && (
          <>
            暂时无法连接服务，或返回格式不符合约定：{errorMessage(state.error)}
          </>
        )}
      </div>
      <details className="connection-details"><summary>连接说明</summary><p>
        连接状态是最近一次检查的快照，不代表模型、路线服务或助手已就绪；业务修改后可重新检查。
      </p></details>
      <button
        className="text-button"
        disabled={state.kind === 'loading'}
        onClick={() => {
          setState({ kind: 'loading' })
          setAttempt((value) => value + 1)
        }}
      >
        重新检查连接
      </button>
    </section>
  )
}
