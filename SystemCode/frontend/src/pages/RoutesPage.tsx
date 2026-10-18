import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { usePlanningRun } from '../planning/runContext'
import RouteMap from '../components/RouteMap'
import { useApi } from '../api/context'
import { createOperation, type Operation } from '../api/client'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { formatSingaporeTime } from '../api/format'
import { ErrorState, LoadingState } from '../components/RequestState'
import { crewColor } from '../map/geography'

type CrewOperation = {
  id: string
  operation: Operation<Omit<Model<'CrewPatch'>, 'request_id'>>
}
type Inputs = { crews: Model<'CrewList'>; snapshot: Model<'TaskSnapshot'> }
type Plans = Partial<Record<'ga' | 'greedy', Model<'RoutePlan'> | null>>
const algorithms = ['ga', 'greedy'] as const

export default function RoutesPage() {
  const { api, mode } = useApi()
  const { rememberRun } = usePlanningRun()
  const [mapAlgorithm, setMapAlgorithm] = useState<'ga' | 'greedy'>('ga')
  const [inputs, setInputs] = useState<Inputs | null>(null)
  const [plans, setPlans] = useState<Plans>({})
  const [planError, setPlanError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState('')
  const [ready, setReady] = useState(false)
  const [crewResult, setCrewResult] = useState<Model<'CrewMutation'> | null>(
    null,
  )
  const [calculation, setCalculation] =
    useState<Model<'RecalculationResult'> | null>(null)
  const [pendingCrew, setPendingCrew] = useState<CrewOperation | null>(null)
  const [unknownPlan, setUnknownPlan] = useState(false)
  const [checkedUnknown, setCheckedUnknown] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  const running = useRef(false)
  const mounted = useRef(true)
  const controller = useRef<AbortController | null>(null)

  async function readInputs(signal: AbortSignal, expected?: number) {
    const crews = await api.crews({ signal })
    if (expected !== undefined && crews.input_revision !== expected)
      throw new ApiError('stale_input_revision', 'Input changed', 409, 'http')
    const snapshot = await api.snapshot(crews.input_revision, { signal })
    if (snapshot.input_revision !== crews.input_revision)
      throw new ApiError(
        'contract_mismatch',
        'Inconsistent snapshot',
        0,
        'contract',
      )
    if (mounted.current && !signal.aborted) {
      setInputs({ crews, snapshot })
      setReady(true)
    }
  }
  async function readPlans(signal: AbortSignal) {
    const results = await Promise.allSettled(
      algorithms.map((algorithm) => api.latestPlan(algorithm, { signal })),
    )
    if (!mounted.current || signal.aborted) return false
    let failure: unknown = null
    const next: Plans = {}
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') next[algorithms[index]] = result.value
      else if (
        result.reason instanceof ApiError &&
        result.reason.code === 'route_plan_not_found'
      )
        next[algorithms[index]] = null
      else failure = result.reason
    })
    setPlans((previous) => ({ ...previous, ...next }))
    setPlanError(failure)
    return failure === null
  }
  async function refresh() {
    if (running.current || pendingCrew) return
    running.current = true
    setBusy('正在读取输入与已保存方案…')
    setReady(false)
    setError(null)
    controller.current = new AbortController()
    const signal = controller.current.signal
    try {
      await readInputs(signal)
      const checked = await readPlans(signal)
      if (mounted.current && !signal.aborted && unknownPlan) {
        setCheckedUnknown(checked)
        setAcknowledged(false)
      }
    } catch (err) {
      if (mounted.current && !signal.aborted) setError(err)
    } finally {
      if (!signal.aborted) {
        running.current = false
        if (mounted.current) setBusy('')
      }
    }
  }
  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => {
      mounted.current = false
      controller.current?.abort()
      running.current = false
    }
    // Provider remounts on source change; API identity is stable within this page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])
  useEffect(() => {
    if (!busy && !pendingCrew && !unknownPlan) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy, pendingCrew, unknownPlan])

  async function changeCrew(crew: Model<'CrewRecord'>, retry?: CrewOperation) {
    if (
      running.current ||
      mode !== 'live' ||
      unknownPlan ||
      (!retry && (!ready || pendingCrew))
    )
      return
    const change = retry ?? {
      id: crew.crew_id,
      operation: createOperation({
        expected_version: crew.record_version,
        available: !crew.available,
      }),
    }
    running.current = true
    setBusy('正在保存队伍状态…')
    setError(null)
    setReady(false)
    controller.current = new AbortController()
    let saved = false
    try {
      const result = await api.updateCrew(change.id, change.operation, {
        signal: controller.current.signal,
      })
      if (!mounted.current) return
      saved = true
      setCrewResult(result)
      setPendingCrew(null)
      // Preserve the actual saved state even if the subsequent snapshot read fails.
      setInputs((previous) =>
        previous
          ? {
              ...previous,
              crews: {
                ...previous.crews,
                input_revision: result.input_revision,
                crews: previous.crews.crews.map((item) =>
                  item.crew_id === result.crew.crew_id ? result.crew : item,
                ),
              },
            }
          : previous,
      )
      await readInputs(controller.current.signal, result.input_revision)
      await readPlans(controller.current.signal)
    } catch (err) {
      if (!mounted.current) return
      setError(err)
      if (!saved && err instanceof ApiError && err.outcomeUnknown)
        setPendingCrew(change)
      else setPendingCrew(null)
    } finally {
      running.current = false
      if (mounted.current) setBusy('')
    }
  }
  async function recalculate() {
    if (
      running.current ||
      mode !== 'live' ||
      !ready ||
      !inputs ||
      pendingCrew ||
      (unknownPlan && !(checkedUnknown && acknowledged))
    )
      return
    running.current = true
    setBusy('正在计算 GA 与 Greedy…')
    setError(null)
    setCalculation(null)
    setUnknownPlan(false)
    setCheckedUnknown(false)
    setAcknowledged(false)
    controller.current = new AbortController()
    try {
      const result = await api.recalculate(
        { expected_revision: inputs.snapshot.input_revision },
        { signal: controller.current.signal, timeoutMs: 120000 },
      )
      if (!mounted.current) return
      if (
        result.plans.length !== 2 ||
        algorithms.some(
          (algorithm) =>
            result.plans.filter((plan) => plan.algorithm === algorithm)
              .length !== 1,
        ) ||
        result.input_revision !== inputs.snapshot.input_revision
      )
        throw new ApiError(
          'contract_mismatch',
          'Invalid calculation pair',
          0,
          'contract',
          null,
          true,
        )
      setCalculation(result)
      rememberRun(result)
      // The successful response is authoritative; failure reading its plans must not POST again.
      const reads = await Promise.allSettled(
        result.plans.map((plan) =>
          api.plan(plan.plan_id, { signal: controller.current!.signal }),
        ),
      )
      if (!mounted.current) return
      let failure: unknown = null
      reads.forEach((read, index) => {
        if (
          read.status === 'fulfilled' &&
          read.value.plan_id === result.plans[index].plan_id &&
          read.value.input_revision === result.input_revision &&
          read.value.algorithm === result.plans[index].algorithm
        )
          setPlans((previous) => ({
            ...previous,
            [read.value.algorithm]: read.value,
          }))
        else
          failure =
            read.status === 'rejected'
              ? read.reason
              : new ApiError(
                  'contract_mismatch',
                  'Plan mismatch',
                  0,
                  'contract',
                )
      })
      setPlanError(failure)
    } catch (err) {
      if (!mounted.current) return
      setError(err)
      if (
        err instanceof ApiError &&
        err.outcomeUnknown &&
        err.code !== 'travel_matrix_unavailable'
      )
        setUnknownPlan(true)
      if (err instanceof ApiError && err.code === 'stale_input_revision')
        setReady(false)
    } finally {
      running.current = false
      if (mounted.current) setBusy('')
    }
  }
  const locked = !!busy || !!pendingCrew || unknownPlan
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">调度 / 04</p>
        <h1>四队路线</h1>
        <p className="description">
          管理全部配置队伍，核对活动任务后显式重算，并查看保存方案的路线顺序。
        </p>
      </div>
      <nav className="section-links" aria-label="调度页面区域"><a href="#dispatch-map">查看路线地图 ↓</a><a href="#dispatch-controls">队伍与重算 ↓</a></nav>
      <div className="dispatch-board">
      <div className="dispatch-controls" id="dispatch-controls" tabIndex={-1}>
      {mode !== 'live' && (
        <p className="notice">当前为只读模拟快照，不能保存队伍或发起重算。</p>
      )}
      <button
        className="button"
        disabled={!!busy || !!pendingCrew}
        onClick={() => void refresh()}
      >
        {unknownPlan ? '核对输入与已保存方案' : '刷新输入与方案'}
      </button>
      {!!busy && <p role="status">{busy}</p>}
      {!inputs && !error && <LoadingState />}
      {error !== null && <ErrorState error={error} />}
      {!ready && inputs && (
        <p className="notice">
          输入尚未重新核对，不能执行新修改或重算。请刷新并检查。
        </p>
      )}
      {inputs && (
        <div className="planning-console">
          <section className="review-queue crew-management" aria-label="工程队管理">
            <h2>工程队可用状态</h2>
            <p>
              配置队伍共 {inputs.crews.crews.length}{' '}
              支。停用队伍仍保留显示；可用不等于已获分配。
            </p>
            <ul className="crew-grid">
              {inputs.crews.crews.map((crew, index) => (
                <li key={crew.crew_id} className={`crew-card ${crew.available ? '' : 'crew-unavailable'}`} style={{ '--crew': crewColor(crew.crew_id) } as CSSProperties}>
                  <span className="crew-avatar" aria-hidden="true">0{index + 1}</span>
                  <strong>
                    {crew.name}
                  </strong>
                  <span className={`status-badge ${crew.available ? 'status-ready' : ''}`}>{crew.available ? '可用' : '停用'}</span>
                  <details><summary>队伍记录</summary><p>{crew.crew_id} · 记录版本 {crew.record_version} · 基地 {crew.depot_id}</p><p>
                    更新：
                    {crew.updated_at
                      ? formatSingaporeTime(crew.updated_at)
                      : '配置初始状态'}
                  </p></details>
                  <button
                    disabled={locked || !ready || mode !== 'live'}
                    onClick={() => void changeCrew(crew)}
                  >
                    {crew.available ? '停用' : '启用'} {crew.name}
                  </button>
                </li>
              ))}
            </ul>
          </section>
          <section className="review-record planning-control" aria-label="重算控制">
            <h2>核对规划输入</h2>
            <p className="planning-task-count">
              活动任务 {inputs.snapshot.total} 项 · 输入版本{' '}
              {inputs.snapshot.input_revision}
            </p>
            <p className="field-note">
              来源：{inputs.snapshot.source}。完成和取消的任务不进入此快照。
            </p>
            <details>
              <summary>查看本次活动任务</summary>
              <ul>
                {inputs.snapshot.tasks.map((task) => (
                  <li key={task.task_id}>
                    <Link to={`/tasks?task=${task.task_id}`}>
                      {task.task_id}
                    </Link>{' '}
                    · {task.priority}
                  </li>
                ))}
              </ul>
            </details>
            <p className="field-note">
              开始时刻由后端在本次计算开始时确定；GA 与 Greedy
              使用同一输入与矩阵。矩阵来源由后端配置决定；Google
              服务失败不会切换模拟矩阵。
            </p>
            <button
              className="button"
              disabled={
                !!busy ||
                !ready ||
                !!pendingCrew ||
                mode !== 'live' ||
                (unknownPlan && !(checkedUnknown && acknowledged))
              }
              onClick={() => void recalculate()}
            >
              重算 GA 与 Greedy
            </button>
          </section>
        </div>
      )}
      {crewResult && (
        <section className="notice" aria-label="队伍保存结果">
          <h3>
            {crewResult.replayed ? '已恢复队伍修改结果' : '队伍状态已保存'}
          </h3>
          <p>
            {crewResult.crew.name}：
            {crewResult.crew.available ? '可用' : '停用'} · 保存时输入版本{' '}
            {crewResult.input_revision}
          </p>
          <p>
            保存队伍状态不代表重算成功。已有方案需按当前输入版本核对；失败后重算不会重复保存队伍。
          </p>
        </section>
      )}
      {pendingCrew && (
        <section className="notice">
          <p>
            队伍保存结果未知。留在本页使用原请求重试，不要切换来源或刷新页面；重试标识仅保存在内存。
          </p>
          <button
            disabled={!!busy}
            onClick={() => {
              const crew = inputs?.crews.crews.find(
                (item) => item.crew_id === pendingCrew.id,
              )
              if (crew) void changeCrew(crew, pendingCrew)
            }}
          >
            使用原请求重试队伍修改
          </button>
        </section>
      )}
      {unknownPlan && (
        <section className="notice">
          <h3>重算结果尚不确定</h3>
          <p>
            后端可能仍在计算或已经保存。先核对输入与已保存方案；最新方案不能证明属于刚才那次请求。本接口没有幂等重算标识，不会自动重试。
          </p>
          {checkedUnknown && (
            <label>
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              我已核对，仍要发起一次新的计算（可能重复计算）
            </label>
          )}
        </section>
      )}
      {calculation && (
        <section className="notice" aria-label="重算结果">
          <h2>本次重算已完成</h2>
          <p>
            输入版本 {calculation.input_revision} · 任务{' '}
            {calculation.task_count} 项 ·{' '}
            {formatSingaporeTime(calculation.planning_start_at)}
          </p>
          <p>
            行程来源：{calculation.matrix_provider}（
            {calculation.matrix_is_simulated ? '模拟矩阵' : '外部行程数据'}
            ），数据时间 {formatSingaporeTime(calculation.matrix_generated_at)}
          </p>
          <ul>
            {calculation.plans.map((plan) => (
              <li key={plan.plan_id}>
                {plan.algorithm.toUpperCase()} · {plan.plan_id} · 已分配{' '}
                {plan.assigned_task_count} / 未分配 {plan.unassigned_task_count}
              </li>
            ))}
          </ul>
          <p>
            以上两个方案 ID 来自同一次重算响应。后续输入变化仍可能使它们过期。
          </p>
          <Link className="button" to="/comparison">比较本次 GA 与 Greedy</Link>
        </section>
      )}
      </div>
      <div className="dispatch-map" id="dispatch-map" tabIndex={-1}>
      <div className="map-controls">
        <label htmlFor="map-algorithm">地图方案</label>
        <select
          id="map-algorithm"
          value={mapAlgorithm}
          onChange={(event) =>
            setMapAlgorithm(event.target.value as 'ga' | 'greedy')
          }
        >
          <option value="ga">GA</option>
          <option value="greedy">Greedy</option>
        </select>
      </div>
      <RouteMap
        key={plans[mapAlgorithm]?.plan_id ?? mapAlgorithm}
        plan={plans[mapAlgorithm]}
        snapshot={inputs?.snapshot}
        currentRevision={inputs?.crews.input_revision}
        readFailed={planError !== null}
      />
      </div>
      </div>
      <section className="review-record" aria-label="已保存方案">
        <h2>已保存方案快照</h2>
        {planError !== null && (
          <>
            <ErrorState error={planError} />
            <p>
              方案读取失败，保留的旧结果未获重新验证。请刷新查询，不要因此重复计算。
            </p>
          </>
        )}
        <details className="saved-plans-details"><summary>展开 GA / Greedy 的方案编号、状态与未分配原因</summary>
        <div className="comparison-plans">
        {algorithms.map((algorithm) => {
          const plan = plans[algorithm]
          return (
            <section key={algorithm}>
              <h3>{algorithm.toUpperCase()}</h3>
              {plan === undefined ? (
                <p>尚未读取成功。</p>
              ) : plan === null ? (
                <p>尚未生成方案（不等于空任务方案）。</p>
              ) : (
                <>
                  <p className="record-id">
                    {plan.plan_id} · 输入版本 {plan.input_revision}
                  </p>
                  <p>
                    {plan.is_stale ||
                    (inputs &&
                      plan.input_revision !== inputs.crews.input_revision)
                      ? '方案已过期，需要重新规划。'
                      : '此方案与最近读取的输入版本一致；不是实时状态保证。'}
                  </p>
                  <p>
                    行程来源 {plan.matrix_provider} ·{' '}
                    {plan.matrix_is_simulated ? '模拟矩阵' : '外部行程数据'}
                  </p>
                  <ul>
                    {plan.crew_routes.map((route) => (
                      <li key={route.crew_id}>
                        {route.crew_id}：
                        {
                          {
                            assigned: '已分配',
                            idle: '闲置',
                            unavailable: '停用',
                          }[route.status]
                        }{' '}
                        · {route.stops.length} 个任务
                      </li>
                    ))}
                  </ul>
                  <p>未分配 {plan.unassigned_tasks.length} 项</p>
                  <ul>
                    {plan.unassigned_tasks.map((task) => (
                      <li key={task.task_id}>
                        {task.task_id}：{task.reason}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )
        })}
        </div>
        </details>
      </section>
    </>
  )
}
