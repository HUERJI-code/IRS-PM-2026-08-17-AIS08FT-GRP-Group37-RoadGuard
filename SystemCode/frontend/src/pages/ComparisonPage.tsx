import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../api/context'
import { ApiError } from '../api/errors'
import { formatSingaporeTime, stopTime } from '../api/format'
import { ErrorState, LoadingState } from '../components/RequestState'
import { usePlanningRun } from '../planning/runContext'
import { assessPair, numberText, percentageChange, priorities, type Pair, type Plan } from '../planning/comparison'

type MetricRow = { label: string; unit: string; read: (plan: Plan) => number | null; percent?: boolean; note?: string }
const rows: MetricRow[] = [
  { label: '已分配任务', unit: '项', read: (p) => p.metrics.assigned_task_count },
  { label: '未分配任务', unit: '项', read: (p) => p.metrics.unassigned_task_count },
  ...priorities.map((priority) => ({ label: `${priority} 未分配`, unit: '项', read: (p: Plan) => p.metrics.unassigned_by_priority[priority] ?? null })),
  { label: '总行程', unit: '分钟', read: (p) => p.metrics.total_travel_minutes, percent: true, note: '包含基地至首站；返程是否计入以保存配置为准。' },
  { label: '总维修时长', unit: '分钟', read: (p) => p.metrics.total_service_minutes },
  { label: '最晚收工时间', unit: '分钟', read: (p) => p.metrics.makespan_minutes, percent: true, note: '从统一出发时刻到最晚可用队伍结束，按配置含返基地。' },
  { label: '工作量标准差', unit: '分钟', read: (p) => p.metrics.workload_std_minutes, percent: true, note: '可用队伍的行程加维修；闲置计 0，停用不计入。' },
  { label: '优先级加权平均完工时间', unit: '分钟', read: (p) => p.metrics.priority_weighted_completion_minutes, percent: true, note: '来自后端的加权平均值，不是延误。' },
  { label: '有期限的任务', unit: '项', read: (p) => p.metrics.tasks_with_due_at },
  { label: '总延误', unit: '分钟', read: (p) => p.metrics.tasks_with_due_at === 0 ? null : p.metrics.total_lateness_minutes, percent: true, note: '无期限无法计算；有期限时仅统计已分配任务的延误，须同时查看未分配项。' },
  { label: '延误任务', unit: '项', read: (p) => p.metrics.tasks_with_due_at === 0 ? null : p.metrics.late_task_count },
  { label: '目标值', unit: '加权分钟', read: (p) => p.metrics.objective_value, percent: true, note: '后端先比较未分配 P1 / P2 / P3，再比较加权成本，不能只看目标值。' },
  { label: '算法耗时', unit: '毫秒', read: (p) => p.metrics.algorithm_runtime_ms, percent: true, note: '不包含行程矩阵准备或外部 API 等待，不是维修完工时长。' },
]

export default function ComparisonPage() {
  const { api, mode } = useApi()
  const { run } = usePlanningRun()
  const [refresh, setRefresh] = useState(0)
  const [data, setData] = useState<{ pair: Pair; revision: number } | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal }
    async function load() {
      setBusy(true)
      setError(null)
      setData(null)
      try {
        async function read(algorithm: 'ga' | 'greedy') {
          const id = run?.plans.find((p) => p.algorithm === algorithm)?.plan_id
          if (run && !id) throw new ApiError('contract_mismatch', 'Missing pair ID', 0, 'contract')
          try {
            const plan = id ? await api.plan(id, options) : await api.latestPlan(algorithm, options)
            if (plan.algorithm !== algorithm || (id && plan.plan_id !== id)) throw new ApiError('contract_mismatch', 'Wrong plan', 0, 'contract')
            return plan
          } catch (err) {
            if (err instanceof ApiError && err.code === 'route_plan_not_found') return null
            throw err
          }
        }
        const [ga, greedy, health] = await Promise.all([read('ga'), read('greedy'), api.health(options)])
        if (!controller.signal.aborted) setData({ pair: { ga, greedy }, revision: health.input_revision })
      } catch (err) {
        if (!controller.signal.aborted) setError(err)
      } finally {
        if (!controller.signal.aborted) setBusy(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [api, run, refresh])
  const check = data ? assessPair(data.pair, run) : null
  const ga = data?.pair.ga
  const greedy = data?.pair.greedy
  const stale = data && [ga, greedy].some((p) => p && (p.is_stale || p.input_revision !== data.revision))
  return <>
    <div className="page-heading">
      <p className="eyebrow">方案比较 / 05</p><h1>算法比较</h1>
      <p className="description">比较保存的 GA 与 Greedy 结果，先核对同轮依据，再查看任务覆盖与各项指标。</p>
    </div>
    <div className="map-controls"><button className="button" disabled={busy} onClick={() => setRefresh((n) => n + 1)}>重新读取比较</button><Link className="button secondary" to="/routes">前往四队路线重算</Link></div>
    {mode !== 'live' && <p className="notice">只读模拟样例；不代表真实规划或实验结果。</p>}
    {busy && <LoadingState />}
    {error !== null && <><ErrorState error={error} /><p>比较读取失败，未展示未核实的差异；重试只读取方案，不会重新计算。</p></>}
    {data && check && <>
      <section className="notice" aria-label="比较依据">
        <h2>{check.comparable ? '同轮方案已核对' : '暂不能确认可比'}</h2>
        {check.reasons.map((reason) => <p key={reason}>{reason}</p>)}
        {!run && <p>从四队路线发起重算后再进入此页，可保留同轮依据。页面刷新或切换数据来源会清除该依据；不会仅凭相同时间或版本恢复。</p>}
        {run && <p>本轮输入版本 {run.input_revision} · {run.task_count} 项任务 · 矩阵 {run.matrix_provider} · {run.matrix_is_simulated ? '模拟行程' : '外部行程数据'} · 取数时间 {formatSingaporeTime(run.matrix_generated_at)}</p>}
        <p>{stale ? '方案已过期，仅供历史比较；当前安排需要重新规划。' : '状态以本次读取为准，不保证此后输入未变化。'} 最近读取输入版本：{data.revision}。</p>
        {check.comparable && !check.sameCoverage && <p>两方案分配的任务集合不同：保留任务数量差异，时间和目标值仅展示原值，不计算百分比。</p>}
      </section>
      {ga && greedy && <section className="review-record comparison-panel" aria-label="指标比较">
        <h2>指标对照</h2>
        <p className="comparison-mobile-hint">窄屏可左右滑动表格，查看两种算法和变化列。</p>
        <p>变化率 =（GA − Greedy）÷ Greedy；负值表示数值减少，正值表示增加。单项减少不等于整体更优，也不代表金额节省。</p>
        <div className="comparison-scroll" role="region" aria-label="可横向滚动的指标表" tabIndex={0}>
          <table className="comparison-table"><caption>保存方案指标与相对 Greedy 的变化</caption><thead><tr><th scope="col">指标</th><th scope="col">GA</th><th scope="col">Greedy</th><th scope="col">变化</th></tr></thead>
            <tbody>{rows.map((row) => {
              const a = row.read(ga), b = row.read(greedy)
              const showChange = check.comparable && (row.unit === '项' || check.sameCoverage)
              return <tr key={row.label}><th scope="row">{row.label}<small>{row.unit}</small></th><td>{a === null ? '无法计算' : numberText(a)}</td><td>{b === null ? '无法计算' : numberText(b)}</td><td>{!showChange ? '不比较' : row.percent ? percentageChange(a, b) : a === null || b === null ? '无法计算' : `${a - b > 0 ? '+' : ''}${numberText(a - b)} ${row.unit}`}</td></tr>
            })}</tbody>
          </table>
        </div>
        <details><summary>指标口径与限制</summary><ul>{rows.filter((r) => r.note).map((r) => <li key={r.label}><strong>{r.label}：</strong>{r.note}</li>)}</ul></details>
        <p>这是单次在线结果，不能代替多随机种子实验，不能据此宣称 GA 总是更好。</p>
      </section>}
      <div className="comparison-plans">{(['ga', 'greedy'] as const).map((algorithm) => {
        const plan = data.pair[algorithm]
        return <section className="review-record comparison-panel" aria-label={`${algorithm.toUpperCase()} 方案详情`} key={algorithm}>
          <h2>{algorithm === 'ga' ? 'GA' : 'Greedy'} 方案</h2>
          {!plan ? <p>尚未找到保存方案，不等于有效的空任务方案。</p> : <PlanDetails plan={plan} />}
        </section>
      })}</div>
    </>}
  </>
}

function PlanDetails({ plan }: { plan: Plan }) {
  const seeded = plan.algorithm_parameters.seed_with_greedy
  return <>
    <p className="record-id">{plan.plan_id}</p>
    <p>输入版本 {plan.input_revision} · {plan.is_demo ? '课程模拟规划' : '规划结果'} · 任务来源 {plan.task_source}</p>
    <p>行程来源：{plan.matrix_provider}（{plan.matrix_is_simulated ? '模拟矩阵' : '外部行程数据'}）</p>
    <p>开始：{formatSingaporeTime(plan.planning_start_at)}<br />最晚收工：{stopTime(plan.planning_start_at, plan.metrics.makespan_minutes)}</p>
    {plan.algorithm === 'ga' && <p>{seeded === true ? 'GA + Greedy 初始解' : seeded === false ? 'GA 未使用 Greedy 初始解' : '未提供是否使用 Greedy 初始解'}；随机种子 {plan.random_seed ?? '未提供'}。在线设置不能与纯 GA 历史实验混用。</p>}
    <p>返基地：{plan.settings.return_to_depot ? '是' : '否'}；班次：{plan.settings.shift_limit.mode === 'limited' ? `${plan.settings.shift_limit.minutes} 分钟` : '明确不限时'}。保存配置 {plan.settings.config_version}（{plan.settings.is_demo ? '演示假设' : '配置'}）。</p>
    <h3>队伍工作量</h3>
    <ul>{plan.crew_routes.map((route) => <li key={route.crew_id}>{route.crew_id} · {{ assigned: '已分配', idle: '闲置', unavailable: '停用' }[route.status]} · {route.stops.length} 项任务 · {numberText(route.total_work_minutes)} 分钟</li>)}</ul>
    <h3>未分配任务与原因</h3>
    {plan.unassigned_tasks.length === 0 ? <p>未分配 0 项。</p> : <ul>{plan.unassigned_tasks.map((task) => <li key={task.task_id}><Link to={`/tasks?task=${encodeURIComponent(task.task_id)}`}>{task.task_id}</Link> · {task.reason}</li>)}</ul>}
    <details><summary>保存的目标权重与算法参数</summary><pre>{JSON.stringify({ settings: plan.settings, algorithm_parameters: plan.algorithm_parameters, random_seed: plan.random_seed }, null, 2)}</pre></details>
  </>
}
