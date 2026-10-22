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
import InspectionImage from '../components/InspectionImage'

const statuses = {
  active: 'Active',
  completed: 'Completed',
  cancelled: 'Cancelled',
} as const
type Payload = Omit<Model<'TaskPatch'>, 'request_id'>
type Action = 'completed' | 'cancelled' | 'label' | 'location'
const labelName = (key: string) =>
  labels.classes.find((item) => item.label_key === key)?.display_name_zh ?? key

// Loads the source inspection only when opened, so browsing tasks does not fetch every photo.
function TaskPhoto({ inspectionId }: { inspectionId: string }) {
  const { api } = useApi()
  const [open, setOpen] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [inspection, setInspection] =
    useState<Model<'InspectionResponse'> | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    if (!open || inspection) return
    const controller = new AbortController()
    let current = true
    api
      .inspection(inspectionId, { signal: controller.signal })
      .then((value) => {
        if (current) setInspection(value)
      })
      .catch((err) => {
        if (current) setError(err)
      })
    return () => {
      current = false
      controller.abort()
    }
  }, [api, inspectionId, open, inspection, attempt])
  return (
    <details
      className="record-history task-photo"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <h3>View road photo</h3>
      </summary>
      {open &&
        (inspection ? (
          <>
            <InspectionImage inspection={inspection} />
            <p className="field-note">
              The box and label show the original detection; later task label corrections are not drawn on the photo.
            </p>
          </>
        ) : error !== null ? (
          <>
            <ErrorState error={error} />
            <button
              className="text-button"
              onClick={() => {
                setError(null)
                setAttempt((value) => value + 1)
              }}
            >
              Retry loading photo
            </button>
          </>
        ) : (
          <LoadingState />
        ))}
    </details>
  )
}

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
              'Select a label from the shared dictionary.',
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
              'Enter valid coordinates and confirm the road declaration.',
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
          Reload task
        </button>
      </>
    )
  return (
    <section className="review-record" aria-label="Selected task">
      <div className="record-heading"><div><p className="eyebrow">SELECTED TASK</p><h2>Task details</h2></div><span className={`status-badge priority-${task.priority.toLowerCase()}`}>{task.priority} · {statuses[task.status]}</span></div>
      <h3 className="record-title">{labelName(task.damage_label)}</h3>
      <Link className="inline-link" to="/routes">Check crews and recalculate routes →</Link>
      <p className="record-id">
        {task.task_id} · Record version {task.record_version}
      </p>
      <p>Status:{statuses[task.status]}</p>
      <dl className="task-facts">
        <div>
          <dt>Damage label</dt>
          <dd>
            {labelName(task.damage_label)} · {task.damage_label}
          </dd>
        </div>
        <div>
          <dt>Severity / Priority</dt>
          <dd>
            {task.severity} / {task.priority}
          </dd>
        </div>
        <div>
          <dt>Estimated repair duration</dt>
          <dd>
            {task.service_minutes == null
              ? 'Unknown'
              : formatMinutes(task.service_minutes)}
          </dd>
        </div>
        <div>
          <dt>Deadline</dt>
          <dd>
            {task.due_at == null ? 'Not set' : formatSingaporeTime(task.due_at)}
          </dd>
        </div>
        <div>
          <dt>Location (WGS84)</dt>
          <dd>
            {task.latitude}, {task.longitude}
          </dd>
        </div>
        <div>
          <dt>Rule version</dt>
          <dd>{task.rule_version}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatSingaporeTime(task.created_at)}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatSingaporeTime(task.updated_at)}</dd>
        </div>
      </dl>
      <p>Repair recommendation:{task.repair_recommendation}</p>
      <Link to={`/inspections/${task.inspection_id}`}>
        View original inspection and rule evidence
      </Link>
      <TaskPhoto inspectionId={task.inspection_id} />
      <p className="field-note">
        Location is user-declared; correcting it does not rewrite the original inspection. Priority, severity and repair duration follow the frozen inspection rules.
      </p>
      {result && (
        <section className="notice" aria-label="Task save result">
          <h3>{result.replayed ? 'Original request result recovered' : 'Task saved'}</h3>
          <p>Input revision {result.input_revision}</p>
          {result.planning_input_changed || result.replayed ? (
            <p>
              Task inputs have changed or the request was replayed. Existing routes may be stale. Check and replan; this page does not recalculate automatically.
            </p>
          ) : (
            <p>Planning inputs are unchanged. The backend plan remains authoritative for route freshness.</p>
          )}
        </section>
      )}
      {task.status !== 'active' ? (
        <p role="status" className="notice">
          Final-state tasks are read-only, retained in history, excluded from new plans and cannot be reactivated.
        </p>
      ) : (
        <form
          className="upload-form review-form"
          onSubmit={(event) => void submit(event)}
        >
          {mode !== 'live' && (
            <p className="notice">This is a read-only mock snapshot. Tasks cannot be changed.</p>
          )}
          <fieldset disabled={busy || uncertain || conflict || mode !== 'live'}>
            <legend>Edit active task</legend>
            <label htmlFor="task-action">Task action</label>
            <select
              id="task-action"
              value={action}
              onChange={(event) => setAction(event.target.value as Action)}
            >
              <option value="completed">Mark as completed</option>
              <option value="cancelled">Cancel task</option>
              <option value="label">Correct damage label</option>
              <option value="location">Correct task location</option>
            </select>
            {(action === 'completed' || action === 'cancelled') && (
              <p>
                Saving moves this task to a final state, excludes it from new plans and prevents reactivation. Check the task before saving.
              </p>
            )}
            {action === 'label' && (
              <>
                <label htmlFor="task-label">New damage label</label>
                <select
                  id="task-label"
                  required
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                >
                  <option value="">Select a label</option>
                  {labels.classes.map((item) => (
                    <option key={item.label_key} value={item.label_key}>
                      {item.display_name_zh} · {item.label_key}
                    </option>
                  ))}
                </select>
                <p>
                  Shared label dictionary {labels.schema_version}
                  ; Repair advice and duration are recalculated by the backend.
                </p>
              </>
            )}
            {action === 'location' && (
              <>
                <label htmlFor="task-lat">Latitude</label>
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
                <label htmlFor="task-lon">Longitude</label>
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
                  I declare that this location is a public motor road
                </label>
                <p>The backend checks the frozen Jurong boundary. This declaration does not establish automatic road-eligibility verification.</p>
              </>
            )}
          </fieldset>
          {error !== null && <ErrorState error={error} />}
          {conflict && (
            <p className="notice">
              The record or request has changed. Reload and check before choosing a new action; old changes are not retried automatically.
            </p>
          )}
          {uncertain && (
            <p className="notice">
              The save outcome is uncertain. Stay here and retry the original request. Do not switch records, sources or pages; refreshing loses the retry ID.
            </p>
          )}
          <button
            className="button"
            disabled={busy || conflict || mode !== 'live'}
            type="submit"
          >
            {busy
              ? 'Saving task…'
              : uncertain
                ? 'Retry task with original request'
                : 'Save task changes'}
          </button>
        </form>
      )}
      <button
        className="text-button"
        disabled={busy || uncertain}
        onClick={reload}
      >
        Reload and check
      </button>
      <details className="record-history">
        <summary><h3>Task history</h3></summary>
        <ul className="task-history">
          {task.history.map((item) => (
            <li key={item.request_id}>
              <p>
                {item.action === 'created' ? 'Created' : 'Updated'} ·{' '}
                {formatSingaporeTime(item.recorded_at)} · Source{' '}
                {item.actor_source}
              </p>
              <p>Changed fields:{item.changed_fields.join(', ') || 'None'}</p>
              <details>
                <summary>View before and after</summary>
                <p>Before</p>
                <pre>
                  {item.before
                    ? JSON.stringify(item.before, null, 2)
                    : 'None (initial creation)'}
                </pre>
                <p>After</p>
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
        <p className="eyebrow">REPAIR / 03</p>
        <h1>Task workspace</h1>
        <p className="description">
          View repair tasks, rule evidence and history. Complete, cancel or correct active tasks.
        </p>
        </div>
        <div className="page-actions"><Link className="button" to="/routes">Schedule four-crew routes <span aria-hidden="true">→</span></Link></div>
      </div>
      <div className="queue-workspace">
      <section className="review-queue" aria-label="Task list">
        <div className="queue-heading"><h2>Repair tasks</h2><span className="queue-count">{!loading && !error && list ? list.total : '—'}</span></div>
        <div className="queue-toolbar">
        <label htmlFor="task-filter">Status filter</label>
        <select
          id="task-filter"
          value={status}
          disabled={locked}
          onChange={(event) => {
            setStatus(event.target.value as typeof status)
            page(0)
          }}
        >
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
          <option value="all">All</option>
        </select>
        <button className="text-button" disabled={loading} onClick={refresh}>
          Refresh task list
        </button>
        </div>
        {loading && <LoadingState />}
        {error !== null && (
          <>
            <ErrorState error={error} />
            {list && <p>Previous list retained and may be stale; details will be reloaded.</p>}
          </>
        )}
        {list && (
          <>
            <p className="queue-meta">
              Total {list.total} records · Page input revision {list.input_revision}
               (data may change during pagination)
            </p>
            {!loading && !error && !list.items.length && (
              <EmptyState
                message={
                  offset
                    ? 'No tasks on this page. Go to the previous page.'
                    : 'No tasks match this filter.'
                }
              />
            )}
            <ul className="review-list">
              {list.items.map((item) => (
                <li key={item.task_id}>
                  <button
                    className="queue-item-button"
                    aria-label={`${labelName(item.damage_label)}, ${item.priority}, ${statuses[item.status]}, Task ${item.task_id}`}
                    disabled={locked}
                    aria-current={
                      selected === item.task_id ? 'true' : undefined
                    }
                    onClick={() => setParams({ task: item.task_id })}
                  >
                    <span className="queue-item-title"><strong>{labelName(item.damage_label)}</strong><span className={`status-badge priority-${item.priority.toLowerCase()}`}>{item.priority}</span></span>
                    <span className="queue-item-meta">{statuses[item.status]} · {item.service_minutes == null ? 'Duration unknown' : formatMinutes(item.service_minutes)}</span>
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
                Previous page
              </button>
              <span>Page {Math.floor(offset / 20) + 1}</span>
              <button
                disabled={loading || offset + 20 >= list.total}
                onClick={() => page(offset + 20)}
              >
                Next page
              </button>
            </div>
          </>
        )}
      </section>
      <div className="record-pane" ref={detailRef} tabIndex={-1} aria-label="Task details workspace">
      {selected ? (
        <TaskRecord
          key={selected}
          id={selected}
          onSaved={refresh}
          onLock={setLocked}
          onReady={revealSelection}
        />
      ) : (
        <div className="selection-empty"><span className="selection-icon" aria-hidden="true">▤</span><p className="eyebrow">Repair tasks</p><h2>Select a task to get started</h2><p>Select a task to view current details. Completed and cancelled tasks remain under their filters.</p><div className="selection-steps"><span>01 · Check damage and repair time</span><span>02 · Update status or correct details</span><span>03 · Go to four-crew routes to replan</span></div><p className="field-note">Accepted damage enters the task list after inspector upload.</p></div>
      )}
      </div>
      </div>
    </div>
  )
}
