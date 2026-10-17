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
    <section className="data-source" aria-label="数据来源">
      <label htmlFor="data-mode">数据来源</label>
      <select
        id="data-mode"
        value={mode}
        onChange={(event) => setMode(event.target.value as DataMode)}
      >
        <option value="live">实时后端接口</option>
        <option value="normal">模拟 · 正常样例</option>
        <option value="empty">模拟 · 空数据</option>
        <option value="failure">模拟 · 服务失败</option>
        <option value="conflict">模拟 · 版本冲突</option>
      </select>
      <p>
        {mode === 'live'
          ? '读取本机后端；服务失败不会自动切换模拟数据。'
          : '模拟数据 · 固定只读快照，不代表实际业务；修改操作被阻止，不会发送到后端。'}
      </p>
      <details>
        <summary>检查数据接入</summary>
        <p>只读检查活动任务数量与 GA 方案是否存在，不会创建或重新规划。</p>
        <button
          className="text-button"
          disabled={state.kind === 'loading'}
          onClick={() => void inspect()}
        >
          读取当前来源
        </button>
        {state.kind === 'loading' && <LoadingState />}
        {state.kind === 'error' && <ErrorState error={state.error} />}
        {state.kind === 'ready' && (
          <>
            {state.total === 0 ? (
              <EmptyState />
            ) : (
              <p role="status">活动任务：{state.total}</p>
            )}
            {state.plan ? <p>方案：{state.plan}</p> : <NoPlanState />}
          </>
        )}
      </details>
    </section>
  )
}
