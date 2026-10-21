import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { useApi } from '../api/context'
import { parseModel, type Model } from '../api/contracts'
import { formatMinutes, formatSingaporeTime } from '../api/format'
import InspectionImage from '../components/InspectionImage'
import { ErrorState, LoadingState } from '../components/RequestState'
import { homeFor, useAuth } from '../auth/context'
import { replanningMessage } from '../api/replanning'
import labels from '../../../model/label_schema.json'

const statusNames = {
  accepted: 'Accepted',
  pending_review: 'Pending manual review',
  no_detection: 'No damage detected',
  rejected: 'Rejected',
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
        <p className="eyebrow">INSPECTION / DETECTION RESULT</p>
        <h1>Inspection result</h1>
        <p className="record-id">Inspection ID:{inspectionId}</p>
      </div>
      {compact && (
        <p role="status" className="notice">
          Upload successful · {statusNames[compact.status]}
          . Subsequent read failures will not upload the photo again.
        </p>
      )}
      {compact && replanningMessage(location.state?.replanning) && <p role="status" className="notice">{replanningMessage(location.state?.replanning)}</p>}
      {loading && <LoadingState />}
      {failure !== null && <ErrorState error={failure} />}
      {!loading && (failure !== null || taskFailure !== null) && (
        <button className="button" onClick={retry}>
          Reload details
        </button>
      )}
      {detail && (
        <div className="inspection-result">
          <section className={`result-summary inspection-status status-${detail.status}`}>
            <p className="eyebrow">Next step for this inspection</p>
            <h2>{statusNames[detail.status]}</h2>
            {detail.status === 'no_detection' && (
              <p>No task created. No detection does not establish that the road is safe.</p>
            )}
            {detail.status === 'pending_review' && (
              <>
                <p>No active task is created before confirmation. Wait for manual review.</p>
                {role === 'dispatcher' && <Link
                  className="button"
                  to={`/reviews?inspection=${detail.inspection_id}`}
                >
                  Go to review workspace
                </Link>}
              </>
            )}
            {detail.status === 'accepted' && (
              <><p>
                A task is linked. Accepted new tasks trigger automatic GA and Greedy route recalculation. Check the latest saved routes for current assignments; later task or crew changes may require replanning.
              </p>{role === 'dispatcher' && detail.task_id && <Link className="button" to={`/tasks?task=${detail.task_id}`}>View repair task →</Link>}</>
            )}
            {detail.status === 'rejected' && (
              <p>This inspection was rejected. Its record remains available.</p>
            )}
            <p className="field-note">
              Inference source:
              {detail.mode === 'real'
                ? 'Real image · Experimental model'
                : 'Fixed mock detection'}
            </p>
            {detail.review_history.length > 0 && (
              <><p>Manual reviews recorded:{detail.review_history.length} records.</p><p className="field-note">Image labels and confidence retain the original model output. See the linked task for the corrected damage type.</p></>
            )}
          </section>
          <InspectionImage
            key={`${inspectionId}-${attempt}`}
            inspection={detail}
          />
          {taskFailure !== null && (
            <section>
              <h2>Linked task could not load</h2>
              <ErrorState error={taskFailure} />
            </section>
          )}
          {task && (
            <section className="result-summary">
              <h2>Linked task</h2>
              {role === 'dispatcher' && <Link to="/routes">Check crews and recalculate routes</Link>}
              <p className="record-id">{task.task_id}</p>
              <p>
                Label: {labels.classes.find((item) => item.label_key === task.damage_label)?.display_name_zh ?? task.damage_label} · Priority: {task.priority} · Estimated repair:
                {formatMinutes(task.service_minutes)}
              </p>
              <p>{task.repair_recommendation}</p>
              <p>
                Rule version:{task.rule_version} · Current task status:{{ active: 'Active', completed: 'Completed', cancelled: 'Cancelled' }[task.status]}
              </p>
              {role === 'dispatcher' && <Link className="button" to={`/tasks?task=${task.task_id}`}>
                Go to task workspace
              </Link>}
            </section>
          )}
          <details className="inspection-metadata"><summary>Inspection source, location and model record</summary>
            <dl className="task-facts"><div><dt>Photo coordinates (user-declared)</dt><dd>{detail.latitude}, {detail.longitude}</dd></div><div><dt>Created</dt><dd>{formatSingaporeTime(detail.created_at)}</dd></div><div><dt>Model version</dt><dd>{detail.model_version}</dd></div><div><dt>Record version</dt><dd>{detail.record_version}</dd></div></dl>
            <p>Road type is user-declared. The system has not automatically verified road eligibility.</p>
            {detail.auto_acceptance && <p>Auto-acceptance policy:{detail.auto_acceptance.policy_version} · Threshold {detail.auto_acceptance.confidence_threshold} (not accuracy)</p>}
          </details>
          <details className="inspection-rule-record">
            <summary>Rule decision record (original backend evidence)</summary>
            <ul>
              {detail.decision_trace.map((trace, index) => (
                <li key={index}>
                  {trace.message} ({trace.rule_version ?? 'Version not provided'})
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
      <div className="workflow-note">
        <Link className="button" to={homeFor(role)}>
          {role === 'inspector' ? 'Upload another photo' : role === 'crew' ? 'Return to crew workspace' : 'Return to task workspace'}
        </Link>
        {detail && !loading && (
          <button className="text-button" onClick={retry}>
            Refresh details
          </button>
        )}
      </div>
    </>
  )
}
