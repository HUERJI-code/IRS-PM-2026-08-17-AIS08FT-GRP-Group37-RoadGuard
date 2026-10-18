import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import labels from '../../../model/label_schema.json'
import { useApi } from '../api/context'
import { createOperation, type Operation } from '../api/client'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { formatMinutes, formatSingaporeTime } from '../api/format'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components/RequestState'

const statuses = {
  active: '活动',
  completed: '已完成',
  cancelled: '已取消',
} as const
type Payload = Omit<Model<'TaskPatch'>, 'request_id'>
type Action = 'completed' | 'cancelled' | 'label' | 'location'
const labelName = (key: string) =>
  labels.classes.find((item) => item.label_key === key)?.display_name_zh ?? key

function TaskRecord({
  id,
  onSaved,
  onLock,
  onReady,
}: {
  id: string
  onSaved: () => void
  onLock: (value: boolean) => void
  onReady: () => void
}) {
  const { api, mode } = useApi()
  const [task, setTask] = useState<Model<'TaskRecord'> | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [readError, setReadError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const [action, setAction] = useState<Action>('completed')
  const [label, setLabel] = useState('')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [road, setRoad] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [result, setResult] = useState<Model<'TaskMutation'> | null>(null)
  const operation = useRef<Operation<Payload> | null>(null)
  const inFlight = useRef(false)
  const active = useRef(true)
  const submission = useRef<AbortController | null>(null)
  useEffect(() => {
    active.current = true
    return () => {
      active.current = false
      submission.current?.abort()
    }
  }, [])
  useEffect(() => {
    onLock(busy || uncertain)
    return () => onLock(false)
  }, [busy, uncertain, onLock])
  useEffect(() => {
    if (!busy && !uncertain) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy, uncertain])
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api
      .task(id, { signal: controller.signal })
      .then((value) => {
        if (current) {
          setTask(value)
          setLatitude(String(value.latitude))
          setLongitude(String(value.longitude))
        }
      })
      .catch((err) => {
        if (current) setReadError(err)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
      controller.abort()
    }
  }, [api, id, attempt])
  useEffect(() => {
    if (!loading) onReady()
  }, [loading, onReady])
  function reload() {
    operation.current = null
    setTask(null)
    setResult(null)
    setReadError(null)
    setError(null)
    setAction('completed')
    setLabel('')
    setRoad(false)
    setConflict(false)
    setUncertain(false)
    setLoading(true)
    setAttempt((value) => value + 1)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (
      inFlight.current ||
      !task ||
      task.status !== 'active' ||
      mode !== 'live' ||
      conflict
    )
      return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      if (!operation.current) {
        const payload: Payload = { expected_version: task.record_version }
        if (action === 'label') {
          if (!labels.classes.some((item) => item.label_key === label))
            throw new ApiError(
              'validation_error',
              '请选择共享字典中的标签。',
              422,
              'http',
            )
          payload.damage_label = label
        } else if (action === 'location') {
          const lat = Number(latitude),
            lon = Number(longitude)
          if (
            !latitude.trim() ||
            !longitude.trim() ||
            !Number.isFinite(lat) ||
            !Number.isFinite(lon) ||
            lat < -90 ||
            lat > 90 ||
            lon < -180 ||
            lon > 180 ||
            !road
          )
            throw new ApiError(
              'validation_error',
              '请填写有效坐标并确认道路声明。',
              422,
              'http',
            )
          Object.assign(payload, {
            latitude: lat,
            longitude: lon,
            road_type: 'public_motor_road',
          })
        } else payload.status = action
        operation.current = createOperation(payload)
      }
      submission.current = new AbortController()
      const value = await api.updateTask(id, operation.current, {
        signal: submission.current.signal,
      })
      if (!active.current) return
      setTask(value.task)
      setResult(value)
      setUncertain(false)
      operation.current = null
      setLabel('')
      setRoad(false)
      setLatitude(String(value.task.latitude))
      setLongitude(String(value.task.longitude))
      onSaved()
    } catch (err) {
      if (!active.current) return
      setError(err)
      const unknown = err instanceof ApiError && err.outcomeUnknown
      setUncertain(unknown)
      if (!unknown) operation.current = null
      if (
        err instanceof ApiError &&
        [
          'stale_record_version',
          'invalid_state',
          'idempotency_conflict',
        ].includes(err.code)
      )
        setConflict(true)
    } finally {
      inFlight.current = false
      if (active.current) setBusy(false)
    }
  }
  if (loading) return <LoadingState />
  if (!task)
    return (
      <>
        <ErrorState error={readError} />
        <button className="button" onClick={reload}>
          重新读取任务
        </button>
      </>
    )
  return (
    <section className="review-record" aria-label="选中任务">
      <div className="record-heading"><div><p className="eyebrow">已选任务</p><h2>任务详情</h2></div><span className={`status-badge priority-${task.priority.toLowerCase()}`}>{task.priority} · {statuses[task.status]}</span></div>
      <h3 className="record-title">{labelName(task.damage_label)}</h3>
      <Link className="inline-link" to="/routes">核对队伍与重算路线 →</Link>
      <p className="record-id">
        {task.task_id} · 记录版本 {task.record_version}
      </p>
      <p>状态：{statuses[task.status]}</p>
      <dl className="task-facts">
        <div>
          <dt>损伤标签</dt>
          <dd>
            {labelName(task.damage_label)} · {task.damage_label}
          </dd>
        </div>
        <div>
          <dt>严重度 / 优先级</dt>
          <dd>
            {task.severity} / {task.priority}
          </dd>
        </div>
        <div>
          <dt>预计维修时长</dt>
          <dd>
            {task.service_minutes == null
              ? '未知'
              : formatMinutes(task.service_minutes)}
          </dd>
        </div>
        <div>
          <dt>期限</dt>
          <dd>
            {task.due_at == null ? '未设置' : formatSingaporeTime(task.due_at)}
          </dd>
        </div>
        <div>
          <dt>位置（WGS84）</dt>
          <dd>
            {task.latitude}, {task.longitude}
          </dd>
        </div>
        <div>
          <dt>规则版本</dt>
          <dd>{task.rule_version}</dd>
        </div>
        <div>
          <dt>创建时间</dt>
          <dd>{formatSingaporeTime(task.created_at)}</dd>
        </div>
        <div>
          <dt>更新时间</dt>
          <dd>{formatSingaporeTime(task.updated_at)}</dd>
        </div>
      </dl>
      <p>维修建议：{task.repair_recommendation}</p>
      <Link to={`/inspections/${task.inspection_id}`}>
        查看原巡检与规则依据
      </Link>
      <p className="field-note">
        位置由用户声明；纠正任务位置不会改写原巡检。优先级、严重度和工时由巡检冻结规则计算。
      </p>
      {result && (
        <section className="notice" aria-label="任务保存结果">
          <h3>{result.replayed ? '已恢复原请求结果' : '任务已保存'}</h3>
          <p>输入版本 {result.input_revision}</p>
          {result.planning_input_changed || result.replayed ? (
            <p>
              任务输入已变化或请求已重放，已有路线可能过期，需要核对并重新规划；本页不会自动重算。
            </p>
          ) : (
            <p>本次未改变规划输入；路线是否过期仍以后端方案为准。</p>
          )}
        </section>
      )}
      {task.status !== 'active' ? (
        <p role="status" className="notice">
          终态任务只读，保留历史，不参加新规划，不能重新激活。
        </p>
      ) : (
        <form
          className="upload-form review-form"
          onSubmit={(event) => void submit(event)}
        >
          {mode !== 'live' && (
            <p className="notice">当前是只读模拟快照，不能修改任务。</p>
          )}
          <fieldset disabled={busy || uncertain || conflict || mode !== 'live'}>
            <legend>修改活动任务</legend>
            <label htmlFor="task-action">任务操作</label>
            <select
              id="task-action"
              value={action}
              onChange={(event) => setAction(event.target.value as Action)}
            >
              <option value="completed">标记为已完成</option>
              <option value="cancelled">取消任务</option>
              <option value="label">纠正损伤标签</option>
              <option value="location">纠正任务位置</option>
            </select>
            {(action === 'completed' || action === 'cancelled') && (
              <p>
                保存后任务进入终态，退出新规划，不能在本系统重新激活。请核对当前任务后再保存。
              </p>
            )}
            {action === 'label' && (
              <>
                <label htmlFor="task-label">新的损伤标签</label>
                <select
                  id="task-label"
                  required
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                >
                  <option value="">请选择标签</option>
                  {labels.classes.map((item) => (
                    <option key={item.label_key} value={item.label_key}>
                      {item.display_name_zh} · {item.label_key}
                    </option>
                  ))}
                </select>
                <p>
                  共享标签字典 {labels.schema_version}
                  ；维修建议与工时由后端重新计算。
                </p>
              </>
            )}
            {action === 'location' && (
              <>
                <label htmlFor="task-lat">纬度</label>
                <input
                  id="task-lat"
                  type="number"
                  step="any"
                  min="-90"
                  max="90"
                  required
                  value={latitude}
                  onChange={(event) => setLatitude(event.target.value)}
                />
                <label htmlFor="task-lon">经度</label>
                <input
                  id="task-lon"
                  type="number"
                  step="any"
                  min="-180"
                  max="180"
                  required
                  value={longitude}
                  onChange={(event) => setLongitude(event.target.value)}
                />
                <label>
                  <input
                    type="checkbox"
                    required
                    checked={road}
                    onChange={(event) => setRoad(event.target.checked)}
                  />
                  我声明该位置为公共机动车道路
                </label>
                <p>后端校验 Jurong 冻结边界；声明不代表已自动核验道路权限。</p>
              </>
            )}
          </fieldset>
          {error !== null && <ErrorState error={error} />}
          {conflict && (
            <p className="notice">
              记录或请求已变化，请重新读取并检查，再选择新操作；不会自动重试旧修改。
            </p>
          )}
          {uncertain && (
            <p className="notice">
              保存结果尚不确定，请留在本页使用原请求重试。不要切换记录、来源或页面；刷新后无法恢复重试标识。
            </p>
          )}
          <button
            className="button"
            disabled={busy || conflict || mode !== 'live'}
            type="submit"
          >
            {busy
              ? '正在保存任务…'
              : uncertain
                ? '使用原请求重试任务'
                : '保存任务修改'}
          </button>
        </form>
      )}
      <button
        className="text-button"
        disabled={busy || uncertain}
        onClick={reload}
      >
        重新读取并检查
      </button>
      <details className="record-history">
        <summary><h3>任务历史</h3></summary>
        <ul className="task-history">
          {task.history.map((item) => (
            <li key={item.request_id}>
              <p>
                {item.action === 'created' ? '创建' : '修改'} ·{' '}
                {formatSingaporeTime(item.recorded_at)} · 来源{' '}
                {item.actor_source}
              </p>
              <p>变化字段：{item.changed_fields.join('、') || '无'}</p>
              <details>
                <summary>查看前后值</summary>
                <p>修改前</p>
                <pre>
                  {item.before
                    ? JSON.stringify(item.before, null, 2)
                    : '无（首次创建）'}
                </pre>
                <p>修改后</p>
                <pre>{JSON.stringify(item.after, null, 2)}</pre>
              </details>
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}

export default function TaskPage() {
  const { api } = useApi()
  const [params, setParams] = useSearchParams()
  const selected = params.get('task') ?? ''
  const detailRef = useRef<HTMLDivElement>(null)
  const selectionToReveal = useRef(selected)
  useEffect(() => {
    selectionToReveal.current = selected
    if (selected && window.matchMedia?.('(max-width: 760px)').matches) {
      detailRef.current?.focus({ preventScroll: true })
    }
  }, [selected])
  const revealSelection = useCallback(() => {
    // Wait for the full record height: scrolling a short loading pane is clamped.
    // Reveal each selection once, without jumping again after save/retry reads.
    if (!selected || selectionToReveal.current !== selected) return
    selectionToReveal.current = ''
    if (window.matchMedia?.('(max-width: 760px)').matches) {
      detailRef.current?.focus({ preventScroll: true })
      detailRef.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
    }
  }, [selected])
  const [status, setStatus] = useState<keyof typeof statuses | 'all'>('active')
  const [offset, setOffset] = useState(0)
  const [locked, setLocked] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [list, setList] = useState<Model<'TaskList'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api
      .tasks({ status, limit: 20, offset }, { signal: controller.signal })
      .then((value) => {
        if (current) {
          setList(value)
          setError(null)
        }
      })
      .catch((err) => {
        if (current) setError(err)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
      controller.abort()
    }
  }, [api, status, offset, attempt])
  function refresh() {
    setLoading(true)
    setAttempt((value) => value + 1)
  }
  function page(next: number) {
    setLoading(true)
    setList(null)
    setError(null)
    setOffset(next)
  }
  return (
    <div className="review-workspace task-workspace">
      <div className="page-heading">
        <div>
        <p className="eyebrow">维修 / 03</p>
        <h1>任务工作区</h1>
        <p className="description">
          查看维修任务、规则依据与历史，完成、取消或纠正活动任务。
        </p>
        </div>
        <div className="page-actions"><Link className="button" to="/routes">安排四队路线 <span aria-hidden="true">→</span></Link></div>
      </div>
      <div className="queue-workspace">
      <section className="review-queue" aria-label="任务列表">
        <div className="queue-heading"><h2>维修任务</h2><span className="queue-count">{!loading && !error && list ? list.total : '—'}</span></div>
        <div className="queue-toolbar">
        <label htmlFor="task-filter">状态筛选</label>
        <select
          id="task-filter"
          value={status}
          disabled={locked}
          onChange={(event) => {
            setStatus(event.target.value as typeof status)
            page(0)
          }}
        >
          <option value="active">活动</option>
          <option value="completed">已完成</option>
          <option value="cancelled">已取消</option>
          <option value="all">全部</option>
        </select>
        <button className="text-button" disabled={loading} onClick={refresh}>
          刷新任务列表
        </button>
        </div>
        {loading && <LoadingState />}
        {error !== null && (
          <>
            <ErrorState error={error} />
            {list && <p>保留上次列表，可能已过时；详情会重新读取。</p>}
          </>
        )}
        {list && (
          <>
            <p className="queue-meta">
              共 {list.total} 条 · 本页输入版本 {list.input_revision}
              （分页期间数据可能变化）
            </p>
            {!loading && !error && !list.items.length && (
              <EmptyState
                message={
                  offset
                    ? '本页没有任务，请返回上一页。'
                    : '当前筛选下没有任务。'
                }
              />
            )}
            <ul className="review-list">
              {list.items.map((item) => (
                <li key={item.task_id}>
                  <button
                    className="queue-item-button"
                    aria-label={`${labelName(item.damage_label)}，${item.priority}，${statuses[item.status]}，任务 ${item.task_id}`}
                    disabled={locked}
                    aria-current={
                      selected === item.task_id ? 'true' : undefined
                    }
                    onClick={() => setParams({ task: item.task_id })}
                  >
                    <span className="queue-item-title"><strong>{labelName(item.damage_label)}</strong><span className={`status-badge priority-${item.priority.toLowerCase()}`}>{item.priority}</span></span>
                    <span className="queue-item-meta">{statuses[item.status]} · {item.service_minutes == null ? '时长未知' : formatMinutes(item.service_minutes)}</span>
                    <span className="queue-item-id" title={item.task_id}>#{item.task_id.slice(0, 8)} <span aria-hidden="true">↗</span></span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="pagination">
              <button
                disabled={loading || !offset}
                onClick={() => page(Math.max(0, offset - 20))}
              >
                上一页
              </button>
              <span>第 {Math.floor(offset / 20) + 1} 页</span>
              <button
                disabled={loading || offset + 20 >= list.total}
                onClick={() => page(offset + 20)}
              >
                下一页
              </button>
            </div>
          </>
        )}
      </section>
      <div className="record-pane" ref={detailRef} tabIndex={-1} aria-label="任务详情工作区">
      {selected ? (
        <TaskRecord
          key={selected}
          id={selected}
          onSaved={refresh}
          onLock={setLocked}
          onReady={revealSelection}
        />
      ) : (
        <div className="selection-empty"><span className="selection-icon" aria-hidden="true">▤</span><p className="eyebrow">维修任务</p><h2>选择一项任务，开始处理</h2><p>选择任务查看最新详情；已完成和取消的任务保留在对应筛选中。</p><div className="selection-steps"><span>01 · 查看损伤与工时</span><span>02 · 更新状态或纠正信息</span><span>03 · 前往四队路线重新规划</span></div><p className="field-note">巡查员上传后，已接受的损伤会进入任务列表。</p></div>
      )}
      </div>
      </div>
    </div>
  )
}
