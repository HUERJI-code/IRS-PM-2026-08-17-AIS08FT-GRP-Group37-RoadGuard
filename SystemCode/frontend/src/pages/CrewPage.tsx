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
const taskStatus = { active: 'Pending', completed: 'Completed', cancelled: 'Cancelled' } as const

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
      <section className="crew-toolbar crew-page-header" aria-label="Crew workspace">
        <div className="page-heading"><div><p className="eyebrow">{data?.crew.name ?? 'My crew'} · FIELD OPERATIONS</p><h1>Crew workspace</h1><p className="description">Follow the route and record each repair when completed.</p></div></div>
        <button className="button secondary" disabled={loading || locked} onClick={refresh}>Refresh workspace</button>
      </section>
      {loading || (!data && !error) ? <LoadingState /> : error ? <ErrorState error={error} /> : data && (
        !data.plan ? <div className="crew-empty"><h2>No route assigned yet</h2><p>Wait for the central dispatcher to assign a route, then refresh your workspace.</p></div>
        : <CrewRoute key={`${data.crew.crew_id}:${data.plan.plan_id}:${attempt}`} crew={data.crew} plan={data.plan}
          revision={data.input_revision} onLock={setLocked} />
      )}
      <p className="crew-scope-note">This workspace shows only your assigned crew. It uses the central dispatcher’s latest saved GA plan. Contact the dispatcher to change the schedule.</p>
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
        setRevisionError(new ApiError('route_changed', 'Dispatch has updated the route. Refresh the workspace.', 409, 'http'))
      } else setRevisionError(null)
      setReadRevision(fresh.input_revision)
      setCurrentAvailable(fresh.crew.available)
      const next: Record<string, TaskRead> = Object.fromEntries((route?.stops ?? []).map((stop) => {
        const task = fresh.tasks.find((item) => item.task_id === stop.task_id)
        return [stop.task_id, task ? { task } : { error: new ApiError('task_unavailable', 'This task has been reassigned or is temporarily unavailable. Refresh the workspace.', 404, 'http') }]
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
  if (!route) return <EmptyState message={stale ? "Your saved route is stale and no longer available after a task or crew change. Ask the dispatcher to recalculate, then refresh your workspace. Task completion requires a current assigned route." : "This saved plan has no record for your crew. Contact the dispatcher."} />
  return (
    <>
      <section className="crew-banner" style={{ '--crew-accent': crewColor(crew.crew_id) } as CSSProperties} aria-label="Crew work overview">
        <div className="crew-banner-heading"><div><p className="eyebrow">{crew.crew_id} / {plan.algorithm.toUpperCase()}</p><h2>Current route<span>{unavailable ? 'Unavailable' : 'Crew operations'}</span></h2></div><button className="crew-route-shortcut" disabled={locked || loading || !stops.length} onClick={() => { itineraryRef.current?.focus({ preventScroll: true }); itineraryRef.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' }) }}>View {stops.length}-stop route ↓</button></div>
        <div className="crew-progress-label"><span>{loading ? 'Checking task status…' : `Completed ${completed} / ${stops.length}`}</span><span>{loading ? '' : `Pending ${remaining.length}${cancelled ? ` · Cancelled ${cancelled}` : ''}${failed ? ` · Unknown ${failed}` : ''}`}</span></div>
        <progress value={completed} max={Math.max(stops.length, 1)} aria-label="Route completion progress" />
      </section>
      {mode !== 'live' && <p className="notice">This is read-only mock data. Task completion cannot be submitted.</p>}
      {unavailable && <p className="notice">This crew is unavailable. The saved route is for reference only. Ask the dispatcher to check crew status.</p>}
      {stale && <p className="notice" role="status">The route snapshot is stale. Order and estimated times follow the original plan. You can still record completion after checking tasks; contact the dispatcher to replan.</p>}
      {revisionError !== null && <><ErrorState error={revisionError} /><p className="notice">Cannot verify the latest input revision. Route freshness is uncertain; refresh the workspace.</p></>}
      {loading ? <LoadingState /> : stops.length === 0 ? <div className="crew-empty"><h2>{unavailable ? 'Crew currently unavailable' : 'No tasks assigned in this plan'}</h2><p>Crew status:{unavailable ? 'Unavailable' : 'Idle'}. Wait for dispatch instructions.</p></div> : (
        <div className="crew-content">
          <section className="crew-current" ref={detailRef} tabIndex={-1} aria-label="Current repair task">
            <div className="crew-card-heading"><p className="eyebrow">Stop {stop?.sequence} · Current task</p><span className="crew-task-number">#{selected.slice(0, 8)}</span></div>
            {!task ? <><h2>Task details could not load</h2><ErrorState error={reads[selected]?.error} /><button className="button" disabled={locked} onClick={reloadTasks}>Reload task status</button></> : (
              <>
                <div className="crew-task-title"><h2>{labelName(task.damage_label)}</h2><span className={`status-badge priority-${task.priority.toLowerCase()}`}>{task.priority} · {taskStatus[task.status]}</span></div>
                <dl className="crew-task-facts">
                  <div><dt>Estimated repair</dt><dd>{formatMinutes(task.service_minutes)}</dd></div>
                  <div><dt>Planned arrival</dt><dd>{stop ? stopTime(plan.planning_start_at, stop.arrival_minute) : 'Not provided'}</dd></div>
                  <div className="crew-location"><dt>Current task location · WGS84</dt><dd>{task.latitude.toFixed(6)}, {task.longitude.toFixed(6)}</dd></div>
                </dl>
                {stop && (task.latitude !== stop.latitude || task.longitude !== stop.longitude || task.service_minutes !== stop.service_minutes || task.priority !== stop.priority) && <p className="notice">Task location, duration or priority differs from the route snapshot. Check the latest details and ask the dispatcher to replan.</p>}
                <div className="crew-repair"><h3>Repair recommendation</h3><p>{task.repair_recommendation}</p></div>
                {!locked && <div className="crew-detail-links"><Link to={`/inspections/${task.inspection_id}`}>View inspection photo ↗</Link></div>}
                {saved?.task.task_id === selected && <p className="crew-success" role="status">{saved.replayed ? 'Original request confirmed; the task is completed.' : 'Completion saved.'}The record is retained and this task is excluded from future plans.</p>}
                {error !== null && <ErrorState error={error} />}
                {conflict && <p className="notice">The task has changed. Reload and check its status before confirming completion.</p>}
                {uncertain && <p className="notice">The submission outcome is uncertain. Stay here and retry the original request; do not change sources or leave the page.</p>}
                <div className="crew-completion">
                  {task.status === 'active' ? (
                    confirming || uncertain ? <section className="crew-confirm" aria-label="Confirm task completion">
                      <h3>Confirm this repair is complete?</h3><p>Stop {stop?.sequence} · {labelName(task.damage_label)} · #{task.task_id.slice(0, 8)}. The record is retained after submission and cannot be reactivated.</p>
                      <div className="crew-action-row"><button className="button" disabled={busy || conflict || mode !== 'live' || unavailable || revisionError !== null} onClick={() => void complete()}>{busy ? 'Submitting…' : uncertain ? 'Retry original request' : 'Confirm completion'}</button><button className="button secondary" disabled={locked} onClick={() => { setConfirming(false); setError(null) }}>Not now</button></div>
                    </section> : <button className="button crew-complete-button" disabled={mode !== 'live' || unavailable || conflict || revisionError !== null} onClick={() => setConfirming(true)}>✓ Mark as complete</button>
                  ) : <div className="crew-finished"><strong>{taskStatus[task.status]}</strong><p>This task remains in history and is excluded from new route plans.</p>{nextTask && <button className="button" onClick={() => chooseTask(nextTask.task_id)}>View next pending task →</button>}</div>}
                  <button className="text-button" disabled={locked} onClick={reloadTasks}>Reload task status</button>
                </div>
              </>
            )}
          </section>
          <section className="crew-itinerary" ref={itineraryRef} tabIndex={-1} aria-label="Crew stop order">
            <div className="crew-card-heading"><h2>My crew route</h2><span>Stops: {stops.length}</span></div>
            <p className="crew-itinerary-note">Saved stop order. Select a stop to view details.</p>
            <div className="crew-depot"><span aria-hidden="true">◈</span><div><strong>NUS-ISS</strong><small>depot</small></div></div>
            <ol className="crew-stops">{stops.map((item) => {
              const record = reads[item.task_id]?.task
              return <li key={item.task_id}><button className="crew-stop" aria-current={selected === item.task_id ? 'step' : undefined} disabled={locked} onClick={() => chooseTask(item.task_id)} aria-label={`Stop ${item.sequence} ${record ? labelName(record.damage_label) : 'Task loading failed'} ${record ? taskStatus[record.status] : 'Status unknown'}`}>
                <span className={`crew-stop-index ${record?.status === 'completed' ? 'is-complete' : ''}`}>{record?.status === 'completed' ? '✓' : item.sequence}</span><span className="crew-stop-copy"><strong>{record ? labelName(record.damage_label) : 'Task loading failed'}</strong><small>{record ? `${record.priority} · ${formatMinutes(record.service_minutes)} · ${taskStatus[record.status]}` : 'Status unknown. Reload to check'}</small><small>#{item.task_id.slice(0, 8)}</small></span><span aria-hidden="true">›</span>
              </button></li>
            })}</ol>
            <p className="crew-route-end">{plan.settings.return_to_depot ? '↩ Return to NUS-ISS after the planned route' : 'This plan does not require depot return'}</p>
            <CrewRouteMap plan={plan} route={route} selected={selected} />
            <details className="crew-plan-details"><summary>Plan times and sources</summary>
              <p>Departure depot NUS-ISS · Plan start {formatSingaporeTime(plan.planning_start_at)}</p>
              <p>All values below are saved estimates. Completing tasks does not automatically reduce them or recalculate the plan.</p>
              <dl><dt>Travel</dt><dd>{formatMinutes(route.travel_minutes)}</dd><dt>Repair</dt><dd>{formatMinutes(route.service_minutes)}</dd><dt>Total work time</dt><dd>{formatMinutes(route.total_work_minutes)}</dd></dl>
              <p>{plan.matrix_is_simulated ? 'Simulated travel matrix' : 'External travel data'} · {plan.matrix_provider}</p><p className="record-id">{plan.plan_id} · Input revision {plan.input_revision}</p>
            </details>
          </section>
        </div>
      )}
    </>
  )
}
