import { useEffect, useRef, useState } from 'react'
import labels from '../../../model/label_schema.json'
import { useApi } from '../api/context'
import type { Model } from '../api/contracts'
import { formatMinutes } from '../api/format'
import { ApiError } from '../api/errors'
import { ErrorState } from '../components/RequestState'
import { usePlanningRun } from '../planning/runContext'

function feasibilityDetails(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.code !== 'task_change_infeasible' || !error.details || typeof error.details !== 'object') return null
  const details = error.details as { shift_limit_minutes?: unknown; return_to_depot?: unknown }
  const shift = typeof details.shift_limit_minutes === 'number' && Number.isFinite(details.shift_limit_minutes)
    ? `Shift limit: ${formatMinutes(details.shift_limit_minutes)}.`
    : details.shift_limit_minutes === null ? 'No shift limit configured.' : ''
  const depot = typeof details.return_to_depot === 'boolean'
    ? details.return_to_depot ? 'Depot return included.' : 'Depot return not required.' : ''
  return [shift, depot].filter(Boolean).join(' ') || null
}
const taskLabel = (key: string | null | undefined) => labels.classes.find(label => label.label_key === key)?.source_name ?? key ?? 'Task'
type Record = Model<'TaskChangeRecord'>
function Routes({ routes }: { routes: Model<'CrewRoute'>[] }) {
  return <div className="adjustment-routes">{routes.map(route => <article className="adjustment-route" key={route.crew_id}>
    <h4>{route.crew_id} · {route.available ? route.status : 'unavailable'}</h4>
    <p>Travel {formatMinutes(route.travel_minutes)} (depot return {route.return_travel_minutes == null ? 'not required' : formatMinutes(route.return_travel_minutes)}) · Service {formatMinutes(route.service_minutes)} · Total {formatMinutes(route.total_work_minutes)}</p>
    <p>Shift remaining: {route.shift_remaining_minutes == null ? 'Not configured' : formatMinutes(route.shift_remaining_minutes)}</p>
    {!route.stops.length && <p>No assigned tasks.</p>}
    <ol>{route.stops.map(stop => <li key={stop.task_id}>
      <strong>Stop {stop.sequence}: {taskLabel(stop.damage_label)} · {stop.priority}</strong><br />
      <code>{stop.task_id}</code>
      {stop.locked_crew_id && <p className="notice">Locked to {stop.locked_crew_id} for future recalculations</p>}
      <p>Travel {formatMinutes(stop.travel_minutes_from_previous)} · Service {formatMinutes(stop.service_minutes)} · Completion offset {formatMinutes(stop.completion_minute)}</p>
    </li>)}</ol>
  </article>)}</div>
}
export default function TaskAdjustmentPanel() {
  const { api, mode } = useApi()
  const { run, rememberRun } = usePlanningRun()
  const [planId, setPlanId] = useState(run?.plans.find(p => p.algorithm === 'ga')?.plan_id ?? '')
  const [plan, setPlan] = useState<Model<'RoutePlan'> | null>(null)
  const [taskId, setTaskId] = useState('')
  const [target, setTarget] = useState('')
  const [kind, setKind] = useState<'reassign' | 'cancel_task'>('reassign')
  const [record, setRecord] = useState<Record | null>(null)
  const [items, setItems] = useState<Record[]>([])
  const [recovery, setRecovery] = useState('')
  const [readAt, setReadAt] = useState(() => Date.now())
  const [checked, setChecked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const operation = useRef<Model<'TaskChangePreview'> | null>(null)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  function clear() { setRecord(null); setChecked(false); setError(null); operation.current = null }
  async function act(work: (signal: AbortSignal) => Promise<void>) {
    if (busy || mode !== 'live') return
    const c = new AbortController(); controller.current = c; setBusy(true); setError(null)
    try { await work(c.signal) } catch (e) { if (!c.signal.aborted) setError(e) }
    finally { if (!c.signal.aborted) setBusy(false) }
  }
  function show(value: Record) { setRecord(value); setChecked(false); setReadAt(Date.now()); if (value.status === 'confirmed') setPlan(null) }
  async function load(latest: boolean, signal: AbortSignal) {
    clear(); setPlan(null); setTaskId(''); setTarget('')
    const value = latest ? await api.latestPlan('ga', { signal }) : await api.plan(planId.trim(), { signal })
    if (!signal.aborted) { setPlan(value); setPlanId(value.plan_id) }
  }
  async function preview(signal: AbortSignal) {
    if (!plan) return
    operation.current ??= { request_id: crypto.randomUUID(), based_on_plan_id: plan.plan_id, action: kind, task_id: taskId, target_crew_id: kind === 'reassign' ? target : null }
    const value = await api.previewTaskChange(operation.current, { signal })
    if (!signal.aborted) show(value)
  }
  async function operate(action: 'confirm' | 'cancel' | 'replan', signal: AbortSignal) {
    if (!record) return
    const value = action === 'confirm' ? await api.confirmTaskChange(record.change_id, { expected_version: record.record_version }, { signal })
      : action === 'cancel' ? await api.cancelTaskChange(record.change_id, { expected_version: record.record_version }, { signal })
      : await api.replanTaskChange(record.change_id, { attempt_id: crypto.randomUUID() }, { signal, timeoutMs: 120000 })
    if (!signal.aborted) {
      show(value)
      if (action === 'confirm') setPlan(null)
      if (value.result) { rememberRun(value.result); setPlan(null) }
    }
  }
  const expired = record?.status === 'pending' && new Date(record.expires_at).getTime() <= readAt
  const running = record?.replan_status === 'running' && record.replan_lease_until && new Date(record.replan_lease_until).getTime() > readAt
  const source = plan?.crew_routes.find(route => route.stops.some(stop => stop.task_id === taskId))
  return <section className="change-panel" aria-label="Task adjustments">
    <h2>Task adjustments</h2>
    <p>Load a saved plan to inspect all crews. Preview a task move or cancellation, then confirm. Confirmed crew assignments stay locked during future recalculations, including when new tasks arrive.</p>
    {mode !== 'live' && <p className="notice">Task changes require the live backend.</p>}
    <fieldset disabled={busy || mode !== 'live'} className="change-form">
      <label htmlFor="task-change-plan">Task adjustment plan ID</label>
      <input id="task-change-plan" value={planId} onChange={e => { setPlanId(e.target.value); setPlan(null); setTaskId(''); clear() }} />
      <div className="assistant-actions"><button className="button secondary" disabled={!/^plan-[0-9a-f]{32}$/.test(planId.trim())} onClick={() => void act(s => load(false, s))}>Load this plan</button>
        <button className="button secondary" onClick={() => void act(s => load(true, s))}>Load latest GA plan</button></div>
    </fieldset>
    {plan && <><h3>Loaded plan <code>{plan.plan_id}</code></h3><p>Input revision {plan.input_revision} · {plan.algorithm.toUpperCase()} · {plan.matrix_is_simulated ? 'Simulated travel' : 'External travel data'}</p>
      {plan.is_stale && <p role="alert">This plan is stale. Recalculate in Routes, then load the current plan before making changes.</p>}
      <Routes routes={plan.crew_routes} />
      {plan.unassigned_tasks.length > 0 && <p className="notice">{plan.unassigned_tasks.length} tasks are unassigned. Unassigned active tasks can be cancelled below.</p>}
      <fieldset className="change-form" disabled={busy || plan.is_stale || mode !== 'live'}>
        <label htmlFor="task-change-action">Task action</label><select id="task-change-action" value={kind} onChange={e => { setKind(e.target.value as typeof kind); setTaskId(''); clear() }}><option value="reassign">Move task to another crew</option><option value="cancel_task">Cancel active task</option></select>
        <label htmlFor="task-change-task">Task to adjust</label><select id="task-change-task" value={taskId} onChange={e => { setTaskId(e.target.value); setTarget(''); clear() }}><option value="">Select a task</option>{plan.crew_routes.flatMap(route => route.stops.map(stop => <option key={stop.task_id} value={stop.task_id}>{route.crew_id} / Stop {stop.sequence} / {taskLabel(stop.damage_label)} / {stop.task_id}</option>))}{kind === 'cancel_task' && plan.unassigned_tasks.map(task => <option key={task.task_id} value={task.task_id}>Unassigned / {task.task_id}</option>)}</select>
        {kind === 'reassign' && <><label htmlFor="task-change-target">Target crew</label><select id="task-change-target" value={target} onChange={e => { setTarget(e.target.value); clear() }}><option value="">Select a crew</option>{plan.crew_routes.map(route => <option key={route.crew_id} value={route.crew_id} disabled={!route.available || route.crew_id === source?.crew_id}>{route.crew_id}{!route.available ? ' (unavailable)' : route.crew_id === source?.crew_id ? ' (current crew)' : ''}</option>)}</select></>}
        <button className="button" disabled={!taskId || (kind === 'reassign' && !target)} onClick={() => void act(preview)}>Preview task change</button>
      </fieldset></>}
    {busy && <p role="status">Processing. Leaving the page does not undo dispatched operations.</p>}
    {error !== null && <><ErrorState error={error} />{error instanceof ApiError && error.code === 'task_change_infeasible' && <p role="alert">{error.message}</p>}{feasibilityDetails(error) && <p>{feasibilityDetails(error)}</p>}{error instanceof ApiError && (error.outcomeUnknown || error.kind === 'network' || error.kind === 'timeout') && <p>Check the saved change record after a connection failure before retrying.</p>}</>}
    {record && <article className="change-preview" aria-label="Task preview and result"><h3>{record.action === 'cancel_task' ? 'Cancel active task' : `Move task to ${record.target_crew_id}`} · {record.status}</h3><p><code>{record.task_id}</code></p><p>Change ID: <code>{record.change_id}</code> · Record version {record.record_version}</p>
      <h4>Before</h4><Routes routes={record.before_routes} /><h4>Preview after change</h4><Routes routes={record.after_routes} />
      {expired && <p role="status">This task preview expired. Load the current plan and create a new preview.</p>}{record.status === 'pending' && !expired && <><label className="change-check"><input type="checkbox" checked={checked} disabled={busy} onChange={e => setChecked(e.target.checked)} />I reviewed the task, destination and server-calculated durations. {record.action === 'cancel_task' ? 'Confirmation cancels the active task.' : 'Confirmation locks the assignment for future recalculations.'}</label><div className="assistant-actions"><button className="button" disabled={busy || !checked || mode !== 'live'} onClick={() => void act(s => operate('confirm', s))}>Confirm task change</button><button className="button secondary" disabled={busy || mode !== 'live'} onClick={() => void act(s => operate('cancel', s))}>Discard task preview</button></div></>}
      {record.status === 'confirmed' && <><p>Saved at input revision {record.applied_revision}. Previous routes are stale. Recalculate explicitly to create current routes.</p>{record.replan_error_code && <ErrorState error={new ApiError(record.replan_error_code, 'Recalculation failed', 503, 'http')} />}{running && <p>Recalculation is running. Refresh the saved result. Recovery is available after {record.replan_lease_until}.</p>}{!record.result && <button className="button" disabled={busy || !!running || mode !== 'live'} onClick={() => void act(s => operate('replan', s))}>Recalculate saved task change</button>}{record.result && <p>New plans saved. Load the latest GA plan to inspect current routes.</p>}</>}
      <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => void act(async s => { const value = await api.taskChange(record.change_id, { signal: s }); if (!s.aborted) show(value) })}>Refresh task change</button>
    </article>}
    <div className="change-recovery"><h3>Recover task changes</h3><button className="text-button" disabled={busy || mode !== 'live'} onClick={() => void act(async s => { const value = await api.taskChanges({ signal: s }); if (!s.aborted) setItems(value.items) })}>Read my recent task changes</button>
      <ul>{items.map(item => <li key={item.change_id}><button className="text-button" disabled={busy} onClick={() => void act(async s => { const value = await api.taskChange(item.change_id, { signal: s }); if (!s.aborted) show(value) })}>{item.action} · {item.task_id} · {item.status}</button></li>)}</ul>
      <label htmlFor="task-change-recovery">Task change ID</label><input id="task-change-recovery" value={recovery} onChange={e => setRecovery(e.target.value)} /><button className="text-button" disabled={busy || mode !== 'live' || !/^task-change-[0-9a-f]{32}$/.test(recovery.trim())} onClick={() => void act(async s => { const value = await api.taskChange(recovery.trim(), { signal: s }); if (!s.aborted) show(value) })}>Recover task change</button>
    </div>
  </section>
}
