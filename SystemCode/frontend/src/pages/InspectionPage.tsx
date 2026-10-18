import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useApi } from '../api/context'
import { parseModel, type Model } from '../api/contracts'
import { formatMinutes, formatSingaporeTime } from '../api/format'
import InspectionImage from '../components/InspectionImage'
import { ErrorState, LoadingState } from '../components/RequestState'
import { homeFor, useAuth } from '../auth/context'
import labels from '../../../model/label_schema.json'

const statusNames = {
  accepted: '已接受',
  pending_review: '待人工审核',
  no_detection: '未检测到损伤',
  rejected: '已驳回',
}

export default function InspectionPage() {
  const { inspectionId = '' } = useParams()
  const { api } = useApi()
  const role = useAuth()?.session?.user.role ?? 'dispatcher'
  const location = useLocation()
  const [attempt, setAttempt] = useState(0)
  const [detail, setDetail] = useState<Model<'InspectionResponse'> | null>(null)
  const [task, setTask] = useState<Model<'TaskRecord'> | null>(null)
  const [failure, setFailure] = useState<unknown>(null)
  const [taskFailure, setTaskFailure] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  let compact: Model<'InspectionUploadResponse'> | null = null
  try {
    if (location.state?.upload)
      compact = parseModel('InspectionUploadResponse', location.state.upload)
  } catch {
    /* A URL can also be opened without upload navigation state. */
  }
  if (compact?.inspection_id !== inspectionId) compact = null
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    async function read() {
      try {
        const result = await api.inspection(inspectionId, {
          signal: controller.signal,
        })
        if (!active) return
        setDetail(result)
        if (result.task_id && role !== 'inspector') {
          try {
            const linked = await api.task(result.task_id, {
              signal: controller.signal,
            })
            if (active) setTask(linked)
          } catch (error) {
            if (active) setTaskFailure(error)
          }
        }
      } catch (error) {
        if (active) setFailure(error)
      } finally {
        if (active) setLoading(false)
      }
    }
    void read()
    return () => {
      active = false
      controller.abort()
    }
  }, [api, inspectionId, attempt, role])
  function retry() {
    setLoading(true)
    setFailure(null)
    setTaskFailure(null)
    setTask(null)
    setDetail(null)
    setAttempt((n) => n + 1)
  }
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">巡检 / 检测结果</p>
        <h1>巡检结果</h1>
        <p className="record-id">巡检 ID：{inspectionId}</p>
      </div>
      {compact && (
        <p role="status" className="notice">
          上传已成功 · {statusNames[compact.status]}
          。后续读取失败不会重新上传照片。
        </p>
      )}
      {loading && <LoadingState />}
      {failure !== null && <ErrorState error={failure} />}
      {!loading && (failure !== null || taskFailure !== null) && (
        <button className="button" onClick={retry}>
          重新读取详情
        </button>
      )}
      {detail && (
        <div className="inspection-result">
          <section className={`result-summary inspection-status status-${detail.status}`}>
            <p className="eyebrow">本次巡检的下一步</p>
            <h2>{statusNames[detail.status]}</h2>
            {detail.status === 'no_detection' && (
              <p>未创建任务。没有检测结果不等于道路安全。</p>
            )}
            {detail.status === 'pending_review' && (
              <>
                <p>确认前不会创建活动任务。请等待人工复核。</p>
                {role === 'dispatcher' && <Link
                  className="button"
                  to={`/reviews?inspection=${detail.inspection_id}`}
                >
                  前往审核工作区
                </Link>}
              </>
            )}
            {detail.status === 'accepted' && (
              <><p>
                已关联任务；任务与队伍变化后，已有路线可能需要重新规划。本页不会自动重算。
              </p>{role === 'dispatcher' && detail.task_id && <Link className="button" to={`/tasks?task=${detail.task_id}`}>查看维修任务 →</Link>}</>
            )}
            {detail.status === 'rejected' && (
              <p>此巡检已驳回，保留记录供查看。</p>
            )}
            <p className="field-note">
              推理来源：
              {detail.mode === 'real'
                ? '真实图片 · 实验模型'
                : '固定模拟检测'}
            </p>
            {detail.review_history.length > 0 && (
              <><p>已有人工审核记录：{detail.review_history.length} 条。</p><p className="field-note">图片中的标签与置信度保留原始模型输出；人工纠正后的损伤类型见关联任务。</p></>
            )}
          </section>
          <InspectionImage
            key={`${inspectionId}-${attempt}`}
            inspection={detail}
          />
          {taskFailure !== null && (
            <section>
              <h2>关联任务读取失败</h2>
              <ErrorState error={taskFailure} />
            </section>
          )}
          {task && (
            <section className="result-summary">
              <h2>关联任务</h2>
              {role === 'dispatcher' && <Link to="/routes">核对队伍与重算路线</Link>}
              <p className="record-id">{task.task_id}</p>
              <p>
                标签：{labels.classes.find((item) => item.label_key === task.damage_label)?.display_name_zh ?? task.damage_label} · 优先级：{task.priority} · 预计维修：
                {formatMinutes(task.service_minutes)}
              </p>
              <p>{task.repair_recommendation}</p>
              <p>
                规则版本：{task.rule_version} · 当前任务状态：{{ active: '活动', completed: '已完成', cancelled: '已取消' }[task.status]}
              </p>
              {role === 'dispatcher' && <Link className="button" to={`/tasks?task=${task.task_id}`}>
                前往任务工作区
              </Link>}
            </section>
          )}
          <details className="inspection-metadata"><summary>巡检来源、位置与模型记录</summary>
            <dl className="task-facts"><div><dt>拍摄坐标（用户声明）</dt><dd>{detail.latitude}, {detail.longitude}</dd></div><div><dt>创建时间</dt><dd>{formatSingaporeTime(detail.created_at)}</dd></div><div><dt>模型版本</dt><dd>{detail.model_version}</dd></div><div><dt>记录版本</dt><dd>{detail.record_version}</dd></div></dl>
            <p>道路类型由用户声明，系统未自动核验道路权限。</p>
            {detail.auto_acceptance && <p>自动接受策略：{detail.auto_acceptance.policy_version} · 阈值 {detail.auto_acceptance.confidence_threshold}（不是准确率）</p>}
          </details>
          <details className="inspection-rule-record">
            <summary>规则决策记录（后端原始依据）</summary>
            <ul>
              {detail.decision_trace.map((trace, index) => (
                <li key={index}>
                  {trace.message}（{trace.rule_version ?? '未提供版本'}）
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
      <div className="workflow-note">
        <Link className="button" to={homeFor(role)}>
          {role === 'inspector' ? '上传另一张照片' : role === 'crew' ? '返回本队工作台' : '返回任务工作区'}
        </Link>
        {detail && !loading && (
          <button className="text-button" onClick={retry}>
            刷新详情
          </button>
        )}
      </div>
    </>
  )
}
