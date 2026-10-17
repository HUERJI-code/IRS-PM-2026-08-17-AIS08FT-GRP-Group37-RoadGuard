import { useEffect, useRef, useState, type FormEvent } from 'react'
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
import InspectionImage from '../components/InspectionImage'

type ReviewPayload = Omit<Model<'ReviewRequest'>, 'request_id'>

function ReviewRecord({
  id,
  onReviewed,
  onLockChange,
}: {
  id: string
  onReviewed: () => void
  onLockChange: (locked: boolean) => void
}) {
  const { api, mode } = useApi()
  const [attempt, setAttempt] = useState(0)
  const [inspection, setInspection] =
    useState<Model<'InspectionResponse'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [readError, setReadError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const [action, setAction] = useState<'confirm' | 'correct' | 'dismiss'>(
    'confirm',
  )
  const [label, setLabel] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [result, setResult] =
    useState<Model<'InspectionMutationResponse'> | null>(null)
  const operation = useRef<Operation<ReviewPayload> | null>(null)
  const inFlight = useRef(false)
  const active = useRef(true)
  const submission = useRef<AbortController | null>(null)

  useEffect(() => {
    onLockChange(busy || uncertain)
    return () => onLockChange(false)
  }, [busy, uncertain, onLockChange])
  useEffect(() => {
    active.current = true
    return () => {
      active.current = false
      submission.current?.abort()
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api
      .inspection(id, { signal: controller.signal })
      .then((value) => {
        if (current) setInspection(value)
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
    if (!busy && !uncertain) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy, uncertain])

  function reload() {
    operation.current = null
    setInspection(null)
    setResult(null)
    setReadError(null)
    setError(null)
    setAction('confirm')
    setLabel('')
    setNote('')
    setConflict(false)
    setUncertain(false)
    setLoading(true)
    setAttempt((n) => n + 1)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (
      inFlight.current ||
      !inspection ||
      inspection.status !== 'pending_review' ||
      mode !== 'live' ||
      conflict
    )
      return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      if (!operation.current) {
        const payload: ReviewPayload = {
          expected_version: inspection.record_version,
          action,
        }
        if (action !== 'dismiss') {
          const detection = inspection.detections[0]
          if (!detection)
            throw new ApiError(
              'invalid_detection_selection',
              '没有可审核的检测对象。',
              422,
              'http',
            )
          payload.detection_id = detection.detection_id
        }
        if (action === 'correct') {
          if (!labels.classes.some((item) => item.label_key === label))
            throw new ApiError(
              'validation_error',
              '请选择纠正标签。',
              422,
              'http',
            )
          payload.damage_label = label
        }
        if (note.trim()) payload.note = note.trim()
        operation.current = createOperation(payload)
      }
      submission.current = new AbortController()
      const value = await api.review(id, operation.current, {
        signal: submission.current.signal,
      })
      if (!active.current) return
      setInspection(value.inspection)
      setResult(value)
      setUncertain(false)
      operation.current = null
      onReviewed()
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
  if (!inspection)
    return (
      <>
        <ErrorState error={readError} />
        <button className="button" onClick={reload}>
          重新读取巡检
        </button>
      </>
    )
  const pending = inspection.status === 'pending_review'
  return (
    <section className="review-record" aria-label="选中巡检">
      <h2>巡检详情</h2>
      <p className="record-id">
        {inspection.inspection_id} · 记录版本 {inspection.record_version}
      </p>
      <p>
        推理来源：
        {inspection.mode === 'real' ? '真实图片 · 实验模型' : '固定模拟检测'} ·
        业务规则：课程演示
      </p>
      <p>
        模型：{inspection.model_version} ·{' '}
        {formatSingaporeTime(inspection.created_at)}
      </p>
      <InspectionImage key={`${id}-${attempt}`} inspection={inspection} />
      <details>
        <summary>查看规则依据</summary>
        <ul>
          {inspection.decision_trace.map((trace, index) => (
            <li key={index}>
              {trace.message}（{trace.rule_version ?? '未提供版本'}）
            </li>
          ))}
        </ul>
      </details>
      {result && (
        <section className="notice" aria-label="审核结果">
          <p>
            图片标签和置信度保留原始检测输出，纠正后的标签见关联任务和审核历史。
          </p>
          <h3>{result.replayed ? '已恢复原请求结果' : '审核已保存'}</h3>
          <p>
            巡检状态：
            {result.inspection.status === 'rejected'
              ? '已驳回'
              : result.inspection.status === 'accepted'
                ? '已接受'
                : result.inspection.status}{' '}
            · 输入版本 {result.input_revision}
          </p>
          {result.task ? (
            <>
              <p>关联任务：{result.task.task_id}</p>
              <p>
                后端标签：{result.task.damage_label} · {result.task.priority} ·
                预计维修 {formatMinutes(result.task.service_minutes)}
              </p>
              <p>规则版本：{result.task.rule_version}</p>
              <Link to="/routes">核对队伍与重算路线</Link>
              <Link to={`/tasks?task=${result.task.task_id}`}>
                查看任务工作区
              </Link>
            </>
          ) : (
            <p>本次结果没有关联任务。</p>
          )}
          {result.planning_input_changed ? (
            <p>规划输入已变化，已有路线需要重新规划；本页没有自动重算。</p>
          ) : (
            <p>本次响应未标记规划输入变化。路线状态仍以后端方案为准。</p>
          )}
        </section>
      )}
      {!pending && (
        <p role="status" className="notice">
          此巡检已处理（{inspection.status}），当前为只读，不能再次审核。
        </p>
      )}
      {inspection.review_history.length > 0 && (
        <section>
          <h3>审核历史</h3>
          <ul>
            {inspection.review_history.map((item) => (
              <li key={item.request_id}>
                {item.action} · {formatSingaporeTime(item.recorded_at)} · 原标签{' '}
                {item.original_damage_label ?? '无'} → 纠正标签{' '}
                {item.corrected_damage_label ?? '未纠正'}
                {item.note && ` · 备注：${item.note}`}
              </li>
            ))}
          </ul>
        </section>
      )}
      {pending && (
        <form
          onSubmit={(event) => void submit(event)}
          className="upload-form review-form"
        >
          {mode !== 'live' && (
            <p className="notice">当前是只读模拟快照，不能保存审核。</p>
          )}
          <fieldset disabled={busy || uncertain || conflict || mode !== 'live'}>
            <legend>人工审核决定</legend>
            <label htmlFor="review-action">操作</label>
            <select
              id="review-action"
              value={action}
              onChange={(event) =>
                setAction(event.target.value as typeof action)
              }
            >
              <option value="confirm">确认当前检测标签</option>
              <option value="correct">纠正损伤标签后接受</option>
              <option value="dismiss">驳回，不创建任务</option>
            </select>
            {action === 'correct' && (
              <>
                <label htmlFor="correct-label">纠正后的标签</label>
                <select
                  id="correct-label"
                  value={label}
                  required
                  onChange={(event) => setLabel(event.target.value)}
                >
                  <option value="">请选择标签</option>
                  {labels.classes.map((item) => (
                    <option key={item.label_key} value={item.label_key}>
                      {item.display_name_zh} · {item.label_key}
                    </option>
                  ))}
                </select>
                <p className="field-note">
                  标签来自共享字典 {labels.schema_version}
                  ；严重度、优先级和工时由后端规则计算。
                </p>
              </>
            )}
            <label htmlFor="review-note">审核备注（可选，最多 500 字符）</label>
            <textarea
              id="review-note"
              rows={3}
              maxLength={500}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <p className="field-note">
              确认/纠正仅选用接口返回的唯一检测对象；原始检测与审核记录由后端保留。
            </p>
          </fieldset>
          {error !== null && <ErrorState error={error} />}
          {conflict && (
            <p className="notice">
              记录或请求已变化。请先重新读取并检查，再作出新的审核决定；不会自动重放旧决定。
            </p>
          )}
          {uncertain && (
            <p className="notice">
              保存结果尚不确定。请留在本页，用原请求重试；不要切换记录、来源或重复创建新审核。刷新页面不能恢复当前重试标识。
            </p>
          )}
          <button
            className="button"
            type="submit"
            disabled={
              busy ||
              conflict ||
              mode !== 'live' ||
              (!uncertain &&
                action !== 'dismiss' &&
                !inspection.detections.length)
            }
          >
            {busy
              ? '正在保存审核…'
              : uncertain
                ? '使用原请求重试审核'
                : '保存审核决定'}
          </button>
          {busy && <p role="status">正在保存，请勿离开当前记录。</p>}
        </form>
      )}
      <div className="workflow-note">
        <button
          className="text-button"
          disabled={busy || uncertain}
          onClick={reload}
        >
          重新读取并检查
        </button>
        <Link to={`/inspections/${id}`}>查看巡检结果页</Link>
      </div>
    </section>
  )
}

export default function ReviewPage() {
  const { api } = useApi()
  const [params, setParams] = useSearchParams()
  const selected = params.get('inspection') ?? ''
  const [offset, setOffset] = useState(0)
  const [recordLocked, setRecordLocked] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [queue, setQueue] = useState<Model<'InspectionListResponse'> | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api
      .inspections(
        { status: 'pending_review', limit: 20, offset },
        { signal: controller.signal },
      )
      .then((value) => {
        if (current) {
          setQueue(value)
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
  }, [api, offset, attempt])
  function refresh() {
    setLoading(true)
    setAttempt((n) => n + 1)
  }
  function page(next: number) {
    setLoading(true)
    setQueue(null)
    setError(null)
    setOffset(next)
  }
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">巡检 / 02</p>
        <h1>人工审核</h1>
        <p className="description">
          检查待审照片，确认、纠正或驳回；业务结论由后端保存。
        </p>
      </div>
      <section className="review-queue" aria-label="待审队列">
        <h2>待审核巡检</h2>
        <button className="text-button" disabled={loading} onClick={refresh}>
          刷新待审队列
        </button>
        {loading && <LoadingState />}
        {error !== null && (
          <>
            <ErrorState error={error} />
            {queue && <p>保留上次列表，可能已过时；进入记录后会重新读取。</p>}
          </>
        )}
        {queue && (
          <>
            <p>共 {queue.total} 条待审记录</p>
            {!loading && !error && !queue.items.length && (
              <EmptyState
                message={
                  offset
                    ? '当前页已无待审记录，请返回上一页。'
                    : '当前没有待审核巡检。'
                }
              />
            )}
            <ul className="review-list">
              {queue.items.map((item) => (
                <li key={item.inspection_id}>
                  <button
                    className="text-button"
                    disabled={recordLocked}
                    aria-current={
                      selected === item.inspection_id ? 'true' : undefined
                    }
                    onClick={() =>
                      setParams({ inspection: item.inspection_id })
                    }
                  >
                    {item.inspection_id}
                  </button>
                  <span>
                    {item.detections[0]?.label ?? '无检测'} ·{' '}
                    {formatSingaporeTime(item.created_at)}
                  </span>
                </li>
              ))}
            </ul>
            <div className="pagination">
              <button
                disabled={loading || offset === 0}
                onClick={() => page(Math.max(0, offset - 20))}
              >
                上一页
              </button>
              <span>第 {Math.floor(offset / 20) + 1} 页</span>
              <button
                disabled={loading || offset + 20 >= queue.total}
                onClick={() => page(offset + 20)}
              >
                下一页
              </button>
            </div>
          </>
        )}
      </section>
      {selected ? (
        <ReviewRecord
          key={selected}
          id={selected}
          onReviewed={refresh}
          onLockChange={setRecordLocked}
        />
      ) : (
        <p className="notice">选择一条待审核巡检查看最新检测与记录版本。</p>
      )}
    </>
  )
}
