import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import labels from '../../../model/label_schema.json'
import { useApi } from '../api/context'
import { createOperation, type Operation } from '../api/client'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { formatMinutes, formatSingaporeTime, stopTime } from '../api/format'
import { EmptyState, ErrorState, LoadingState } from '../components/RequestState'
import CrewRouteMap from '../components/CrewRouteMap'
import { crewColor } from '../map/geography'
import '../crew.css'

type Plan = Model<'CrewWorkspacePlan'>
type Crew = Model<'CrewList'>['crews'][number]
type Task = Model<'TaskRecord'>
type Payload = Omit<Model<'TaskPatch'>, 'request_id'>
type TaskRead = { task: Task; error?: never } | { task?: never; error: unknown }
const labelName = (key: string) => labels.classes.find((item) => item.label_key === key)?.display_name_zh ?? key
const taskStatus = { active: '待完成', completed: '已完成', cancelled: '已取消' } as const

export default function CrewPage() {
  const { api } = useApi()
  const [data, setData] = useState<Model<'CrewWorkspaceResponse'> | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [locked, setLocked] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api.crewWorkspace({ signal: controller.signal })
      .then((value) => { if (current) { setData(value); setError(null) } })
      .catch((err) => { if (current) setError(err) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false; controller.abort() }
  }, [api, attempt])
  function refresh() {
    if (locked) return
    setData(null); setError(null); setLoading(true)
    setAttempt((value) => value + 1)
  }
  return (
    <div className="crew-workspace">
      <section className="crew-toolbar crew-page-header" aria-label="本队工作台">
        <div className="page-heading"><div><p className="eyebrow">{data?.crew.name ?? '我的队伍'} · 现场作业</p><h1>施工队工作台</h1><p className="description">按路线处理任务，完成后及时记录。</p></div></div>
        <button className="button secondary" disabled={loading || locked} onClick={refresh}>刷新工作台</button>
      </section>
      {loading || (!data && !error) ? <LoadingState /> : error ? <ErrorState error={error} /> : data && (
        !data.plan ? <div className="crew-empty"><h2>还没有路线安排</h2><p>请等待中央调度员安排路线，再刷新工作台。</p></div>
        : <CrewRoute key={`${data.crew.crew_id}:${data.plan.plan_id}:${attempt}`} crew={data.crew} plan={data.plan}
          revision={data.input_revision} onLock={setLocked} />
      )}
      <p className="crew-scope-note">工作台仅显示账号所属队伍。路线采用中央调度员最近保存的 GA 方案；如需变更安排，请联系调度员。</p>
    </div>
  )
}

function CrewRoute({ crew, plan, revision, onLock }: {
  crew: Crew; plan: Plan; revision: number; onLock: (locked: boolean) => void
}) {
  const { api, mode } = useApi()
  const route = plan.crew_routes.find((item) => item.crew_id === crew.crew_id)
  const stops = [...(route?.stops ?? [])].sort((a, b) => a.sequence - b.sequence)
  const [reads, setReads] = useState<Record<string, TaskRead>>({})
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState<Model<'TaskMutation'> | null>(null)
  const [readRevision, setReadRevision] = useState(revision)
  const [revisionError, setRevisionError] = useState<unknown>(null)
  const [currentAvailable, setCurrentAvailable] = useState(crew.available)
  const operation = useRef<Operation<Payload> | null>(null)
  const inFlight = useRef(false)
  const mounted = useRef(true)
  const submission = useRef<AbortController | null>(null)
  const detailRef = useRef<HTMLElement>(null)
  const itineraryRef = useRef<HTMLElement>(null)
  const reveal = useRef(false)
  const locked = busy || uncertain
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; submission.current?.abort() }
  }, [])
  useEffect(() => {
    onLock(locked)
    if (!locked) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => { onLock(false); window.removeEventListener('beforeunload', warn) }
  }, [locked, onLock])
  useEffect(() => {
    let current = true
    const controller = new AbortController()
    const options = { signal: controller.signal }
    // One server snapshot contains only this account's crew and task records.
    api.crewWorkspace(options).then((fresh) => {
      if (!current) return
      if (fresh.plan?.plan_id !== plan.plan_id) {
        setRevisionError(new ApiError('route_changed', '调度已更新路线，请刷新工作台。', 409, 'http'))
      } else setRevisionError(null)
      setReadRevision(fresh.input_revision)
      setCurrentAvailable(fresh.crew.available)
      const next: Record<string, TaskRead> = Object.fromEntries((route?.stops ?? []).map((stop) => {
        const task = fresh.tasks.find((item) => item.task_id === stop.task_id)
        return [stop.task_id, task ? { task } : { error: new ApiError('task_unavailable', '任务已重新分配或暂不可读取，请刷新工作台。', 404, 'http') }]
      }))
      setReads(next)
      setSelected((previous) => next[previous] ? previous : [...(route?.stops ?? [])]
        .sort((a, b) => a.sequence - b.sequence).find((stop) => next[stop.task_id]?.task?.status === 'active')?.task_id ?? route?.stops[0]?.task_id ?? '')
    }).catch((err) => { if (current) setRevisionError(err) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false; controller.abort() }
  }, [api, route, attempt, plan.plan_id])
  useEffect(() => {
    if (!reveal.current || loading) return
    reveal.current = false
    if (window.matchMedia?.('(max-width: 760px)').matches) {
      detailRef.current?.focus({ preventScroll: true })
      detailRef.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
    }
  }, [selected, loading])
  function chooseTask(id: string) {
    if (locked) return
    if (id === selected && window.matchMedia?.('(max-width: 760px)').matches) {
      detailRef.current?.focus({ preventScroll: true })
      detailRef.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
    }
    reveal.current = id !== selected
    setSelected(id); setConfirming(false); setError(null); setConflict(false)
    operation.current = null
  }
  function reloadTasks() {
    if (locked) return
    setLoading(true); setError(null); setConfirming(false); setConflict(false)
    operation.current = null
    setAttempt((value) => value + 1)
  }
  const task = reads[selected]?.task
  const stop = stops.find((item) => item.task_id === selected)
  const unavailable = !currentAvailable || route?.available === false || route?.status === 'unavailable'
  async function complete() {
    if (inFlight.current || !task || task.status !== 'active' || mode !== 'live' || unavailable || revisionError !== null || conflict || (!confirming && !uncertain)) return
    inFlight.current = true; setBusy(true); setError(null)
    operation.current ??= createOperation<Payload>({ expected_version: task.record_version, status: 'completed' })
    submission.current = new AbortController()
    try {
      const result = await api.updateTask(task.task_id, operation.current, { signal: submission.current.signal })
      if (!mounted.current) return
      setReads((values) => ({ ...values, [task.task_id]: { task: result.task } }))
      setSaved(result); setUncertain(false); setConfirming(false)
      operation.current = null
    } catch (err) {
      if (!mounted.current) return
      setError(err)
      const unknown = err instanceof ApiError && err.outcomeUnknown
      setUncertain(unknown)
      if (!unknown) operation.current = null
      if (err instanceof ApiError && ['stale_record_version', 'invalid_state', 'idempotency_conflict', 'not_found', 'forbidden'].includes(err.code)) setConflict(true)
    } finally {
      inFlight.current = false
      if (mounted.current) setBusy(false)
    }
  }
  const completed = stops.filter((item) => reads[item.task_id]?.task?.status === 'completed').length
  const remaining = stops.filter((item) => reads[item.task_id]?.task?.status === 'active')
  const cancelled = stops.filter((item) => reads[item.task_id]?.task?.status === 'cancelled').length
  const failed = stops.filter((item) => reads[item.task_id]?.error !== undefined).length
  const stale = plan.is_stale || plan.input_revision !== readRevision || !!saved
  const nextTask = remaining.find((item) => item.task_id !== selected)
  if (!route) return <EmptyState message="该保存方案中没有此队伍记录，请联系调度人员核对。" />
  return (
    <>
      <section className="crew-banner" style={{ '--crew-accent': crewColor(crew.crew_id) } as CSSProperties} aria-label="本队工作概览">
        <div className="crew-banner-heading"><div><p className="eyebrow">{crew.crew_id} / {plan.algorithm.toUpperCase()}</p><h2>本次路线<span>{unavailable ? '已停用' : '本队作业'}</span></h2></div><button className="crew-route-shortcut" disabled={locked || loading || !stops.length} onClick={() => { itineraryRef.current?.focus({ preventScroll: true }); itineraryRef.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' }) }}>查看 {stops.length} 站路线 ↓</button></div>
        <div className="crew-progress-label"><span>{loading ? '正在核对任务状态…' : `已完成 ${completed} / ${stops.length}`}</span><span>{loading ? '' : `待完成 ${remaining.length}${cancelled ? ` · 已取消 ${cancelled}` : ''}${failed ? ` · 未知 ${failed}` : ''}`}</span></div>
        <progress value={completed} max={Math.max(stops.length, 1)} aria-label="本路线完成进度" />
      </section>
      {mode !== 'live' && <p className="notice">当前为只读模拟数据，不能提交任务完成状态。</p>}
      {unavailable && <p className="notice">该队伍已停用，保存的路线仅供查看。请由调度人员核对队伍状态。</p>}
      {stale && <p className="notice" role="status">路线快照已过期，顺序与预计时间沿用原方案。核对任务后仍可记录完成，请联系调度员重新规划。</p>}
      {revisionError !== null && <><ErrorState error={revisionError} /><p className="notice">无法核对最新输入版本；路线是否过期尚不确定，请刷新工作台。</p></>}
      {loading ? <LoadingState /> : stops.length === 0 ? <div className="crew-empty"><h2>{unavailable ? '当前队伍不可用' : '本方案没有安排任务'}</h2><p>本队处于{unavailable ? '停用' : '闲置'}状态，请等待调度安排。</p></div> : (
        <div className="crew-content">
          <section className="crew-current" ref={detailRef} tabIndex={-1} aria-label="当前维修任务">
            <div className="crew-card-heading"><p className="eyebrow">第 {stop?.sequence} 站 · 当前任务</p><span className="crew-task-number">#{selected.slice(0, 8)}</span></div>
            {!task ? <><h2>任务详情读取失败</h2><ErrorState error={reads[selected]?.error} /><button className="button" disabled={locked} onClick={reloadTasks}>重新读取任务状态</button></> : (
              <>
                <div className="crew-task-title"><h2>{labelName(task.damage_label)}</h2><span className={`status-badge priority-${task.priority.toLowerCase()}`}>{task.priority} · {taskStatus[task.status]}</span></div>
                <dl className="crew-task-facts">
                  <div><dt>预计维修</dt><dd>{formatMinutes(task.service_minutes)}</dd></div>
                  <div><dt>方案预计到达</dt><dd>{stop ? stopTime(plan.planning_start_at, stop.arrival_minute) : '未提供'}</dd></div>
                  <div className="crew-location"><dt>任务当前位置 · WGS84</dt><dd>{task.latitude.toFixed(6)}, {task.longitude.toFixed(6)}</dd></div>
                </dl>
                {stop && (task.latitude !== stop.latitude || task.longitude !== stop.longitude || task.service_minutes !== stop.service_minutes || task.priority !== stop.priority) && <p className="notice">任务位置、工时或优先级与路线快照不同。请核对最新详情，并联系调度重新规划。</p>}
                <div className="crew-repair"><h3>维修建议</h3><p>{task.repair_recommendation}</p></div>
                {!locked && <div className="crew-detail-links"><Link to={`/inspections/${task.inspection_id}`}>查看巡检照片 ↗</Link></div>}
                {saved?.task.task_id === selected && <p className="crew-success" role="status">{saved.replayed ? '已确认原请求结果，任务已完成。' : '完成状态已保存。'}记录保留，后续规划会排除此任务。</p>}
                {error !== null && <ErrorState error={error} />}
                {conflict && <p className="notice">任务已被修改，请重新读取任务状态并核对，再确认完成。</p>}
                {uncertain && <p className="notice">提交结果尚不确定。请留在本页，用原请求重试；不要切换数据来源或离开页面。</p>}
                <div className="crew-completion">
                  {task.status === 'active' ? (
                    confirming || uncertain ? <section className="crew-confirm" aria-label="确认任务完成">
                      <h3>确认这项维修已完成？</h3><p>第 {stop?.sequence} 站 · {labelName(task.damage_label)} · #{task.task_id.slice(0, 8)}。提交后保留记录，不能重新激活。</p>
                      <div className="crew-action-row"><button className="button" disabled={busy || conflict || mode !== 'live' || unavailable || revisionError !== null} onClick={() => void complete()}>{busy ? '正在提交…' : uncertain ? '用原请求重试' : '确认完成'}</button><button className="button secondary" disabled={locked} onClick={() => { setConfirming(false); setError(null) }}>暂不提交</button></div>
                    </section> : <button className="button crew-complete-button" disabled={mode !== 'live' || unavailable || conflict || revisionError !== null} onClick={() => setConfirming(true)}>✓ 标记为完成</button>
                  ) : <div className="crew-finished"><strong>{taskStatus[task.status]}</strong><p>此任务保留历史，不再进入新的路线规划。</p>{nextTask && <button className="button" onClick={() => chooseTask(nextTask.task_id)}>查看下一项待完成任务 →</button>}</div>}
                  <button className="text-button" disabled={locked} onClick={reloadTasks}>重新读取任务状态</button>
                </div>
              </>
            )}
          </section>
          <section className="crew-itinerary" ref={itineraryRef} tabIndex={-1} aria-label="本队停靠顺序">
            <div className="crew-card-heading"><h2>本队路线</h2><span>{stops.length} 站</span></div>
            <p className="crew-itinerary-note">按保存顺序排列，点选一站查看详情。</p>
            <div className="crew-depot"><span aria-hidden="true">◈</span><div><strong>NUS-ISS</strong><small>出发基地</small></div></div>
            <ol className="crew-stops">{stops.map((item) => {
              const record = reads[item.task_id]?.task
              return <li key={item.task_id}><button className="crew-stop" aria-current={selected === item.task_id ? 'step' : undefined} disabled={locked} onClick={() => chooseTask(item.task_id)} aria-label={`第 ${item.sequence} 站 ${record ? labelName(record.damage_label) : '任务读取失败'} ${record ? taskStatus[record.status] : '状态未知'}`}>
                <span className={`crew-stop-index ${record?.status === 'completed' ? 'is-complete' : ''}`}>{record?.status === 'completed' ? '✓' : item.sequence}</span><span className="crew-stop-copy"><strong>{record ? labelName(record.damage_label) : '任务读取失败'}</strong><small>{record ? `${record.priority} · ${formatMinutes(record.service_minutes)} · ${taskStatus[record.status]}` : '状态未知，请重新读取'}</small><small>#{item.task_id.slice(0, 8)}</small></span><span aria-hidden="true">›</span>
              </button></li>
            })}</ol>
            <p className="crew-route-end">{plan.settings.return_to_depot ? '↩ 计划结束后返回 NUS-ISS' : '本方案不要求返回基地'}</p>
            <CrewRouteMap plan={plan} route={route} selected={selected} />
            <details className="crew-plan-details"><summary>方案时间与来源</summary>
              <p>出发基地 NUS-ISS · 方案开始 {formatSingaporeTime(plan.planning_start_at)}</p>
              <p>以下均为保存的计划值，完成任务后不会自动扣减或重算。</p>
              <dl><dt>行程</dt><dd>{formatMinutes(route.travel_minutes)}</dd><dt>维修</dt><dd>{formatMinutes(route.service_minutes)}</dd><dt>总工作时长</dt><dd>{formatMinutes(route.total_work_minutes)}</dd></dl>
              <p>{plan.matrix_is_simulated ? '模拟行程矩阵' : '外部行程数据'} · {plan.matrix_provider}</p><p className="record-id">{plan.plan_id} · 输入版本 {plan.input_revision}</p>
            </details>
          </section>
        </div>
      )}
    </>
  )
}
