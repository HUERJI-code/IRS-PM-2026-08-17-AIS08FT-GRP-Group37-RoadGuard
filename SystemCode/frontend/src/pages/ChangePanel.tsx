import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../api/context'
import type { Model } from '../api/contracts'
import { ApiError, errorMessage } from '../api/errors'
import { formatSingaporeTime } from '../api/format'
import { ErrorState } from '../components/RequestState'
import { usePlanningRun } from '../planning/runContext'

type Change = Model<'ChangeRecord'>
const stateNames: Record<Change['status'], string> = {
  pending: 'Awaiting confirmation', confirmed: 'Crew availability saved', cancelled: 'Cancelled', expired: 'Preview expired', failed: 'Confirmation rejected',
}
const planNames: Record<Change['replan_status'], string> = {
  not_requested: 'Not recalculated', running: 'Recalculating', failed: 'Recalculation failed', succeeded: 'New plans saved',
}

export default function ChangePanel() {
  const { api, mode } = useApi()
  const { run, rememberRun } = usePlanningRun()
  const [planId, setPlanId] = useState(run?.plans.find((p) => p.algorithm === 'ga')?.plan_id ?? '')
  const [instruction, setInstruction] = useState('')
  const [readAt, setReadAt] = useState(() => Date.now())
  const [record, setRecord] = useState<Change | null>(null)
  const [items, setItems] = useState<Change[]>([])
  const [busy, setBusy] = useState(false)
  const [checked, setChecked] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [recoveredId, setRecoveredId] = useState('')
  const preview = useRef<Model<'ChangePreview'> | null>(null)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  const expired = record && new Date(record.expires_at).getTime() <= readAt
  const running = record?.replan_status === 'running' && record.replan_lease_until &&
    new Date(record.replan_lease_until).getTime() > readAt

  function show(next: Change) { setRecord(next); setChecked(false); setReadAt(Date.now()) }
  async function action(work: (signal: AbortSignal) => Promise<void>) {
    if (busy || mode !== 'live') return
    setBusy(true); setError(null)
    const next = new AbortController(); controller.current = next
    try { await work(next.signal) }
    catch (err) { if (!next.signal.aborted) setError(err) }
    finally { if (!next.signal.aborted) setBusy(false) }
  }
  async function create(signal: AbortSignal) {
    preview.current ??= { request_id: crypto.randomUUID(), based_on_plan_id: planId.trim(), instruction: instruction.trim() }
    const next = await api.previewChange(preview.current, { signal })
    if (!signal.aborted) show(next)
  }
  async function operate(operation: 'confirm' | 'cancel' | 'replan', signal: AbortSignal) {
    if (!record) return
    const next = operation === 'replan'
      ? await api.replanChange(record.change_id, { attempt_id: crypto.randomUUID() }, { signal, timeoutMs: 120000 })
      : operation === 'confirm'
        ? await api.confirmChange(record.change_id, { expected_version: record.record_version }, { signal })
        : await api.cancelChange(record.change_id, { expected_version: record.record_version }, { signal })
    if (!signal.aborted) {
      show(next)
      if (next.result) rememberRun(next.result)
    }
  }
  function edit() { preview.current = null; setError(null); setRecord(null); setChecked(false) }
  return <section className="change-panel" aria-label="Crew availability">
    <h2>Crew availability</h2>
    <p>Review the preview and confirm. Confirmation saves crew availability; recalculate separately to generate routes.</p>
    <p className="notice">Use "disable crew-02" or "enable crew-02". Change one crew at a time. Compound commands and road closures are unsupported. This flow does not call GPT.</p>
    {mode !== 'live' && <p role="status">Switch to the live backend to create or confirm changes.</p>}
    <fieldset disabled={busy || mode !== 'live'} className="change-form">
      <label htmlFor="change-plan">Availability plan ID</label>
      <input id="change-plan" value={planId} onChange={(e) => { setPlanId(e.target.value); edit() }} placeholder="Saved current plan" />
      <button className="text-button" onClick={() => void action(async (signal) => {
        const plan = await api.latestPlan('ga', { signal })
        if (!signal.aborted) {
          edit(); setPlanId(plan.plan_id)
          if (plan.is_stale) throw new ApiError('assistant_stale_plan', 'Stale', 409, 'http')
        }
      })}>Read latest availability plan</button>
      <label htmlFor="change-instruction">Availability instruction</label>
      <input id="change-instruction" value={instruction} maxLength={200} onChange={(e) => { setInstruction(e.target.value); edit() }} placeholder="disable crew-02" />
      <button className="button" disabled={!instruction.trim() || !/^plan-[0-9a-f]{32}$/.test(planId.trim())} onClick={() => void action(create)}>Preview availability change</button>
    </fieldset>
    {busy && <p role="status">Processing. Do not submit again. Leaving this page does not undo a dispatched operation.</p>}
    {error !== null && <><ErrorState error={error} /><p>After a connection failure, recover the saved record below. A failed recalculation does not restore availability or retry automatically.</p></>}
    <div className="change-recovery">
      <h3>Recovery</h3>
      <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => void action(async (signal) => {
        const list = await api.changeRequests({ signal }); if (!signal.aborted) setItems(list.items)
      })}>Read my recent availability changes</button>
      {items.length > 0 && <ul>{items.map((item) => <li key={item.change_id}>
        <button className="text-button" disabled={busy} onClick={() => void action(async (signal) => {
          const next = await api.changeRequest(item.change_id, { signal }); if (!signal.aborted) show(next)
        })}>{item.instruction} · {stateNames[item.status]} · {formatSingaporeTime(item.created_at)}</button>
      </li>)}</ul>}
      <label htmlFor="recover-change">Availability change ID</label>
      <input id="recover-change" value={recoveredId} disabled={busy} onChange={(e) => setRecoveredId(e.target.value)} placeholder="change-…" />
      <button className="text-button" disabled={busy || mode !== 'live' || !/^change-[0-9a-f]{32}$/.test(recoveredId.trim())}
        onClick={() => void action(async (signal) => {
          const next = await api.changeRequest(recoveredId.trim(), { signal }); if (!signal.aborted) show(next)
        })}>Recover availability change</button>
    </div>
    {record && <article className="change-preview" aria-label="Availability preview and result">
      <p className="eyebrow">{stateNames[record.status]}</p>
      <h3>{record.crew_id}: {record.before_available ? 'available' : 'unavailable'} → {record.after_available ? 'available' : 'unavailable'}</h3>
      <p>Preview input revision {record.input_revision} · Crew version {record.crew_record_version} · Change record version {record.record_version}</p>
      <p>Change ID: <code>{record.change_id}</code></p>
      <p>Confirmation deadline: {formatSingaporeTime(record.expires_at)}</p>
      <p>{record.warning}</p>
      {record.before_available === record.after_available && <p>Availability is unchanged. Confirmation records the action without increasing the planning revision.</p>}
      {record.error_code && <p role="alert">{errorMessage(new ApiError(record.error_code, 'Rejected', 409, 'http'))} Check the current plan and create a new preview.</p>}
      {record.status === 'pending' && !expired && <>
        <label className="change-check"><input type="checkbox" checked={checked} disabled={busy} onChange={(e) => setChecked(e.target.checked)} />
          I have checked  {record.crew_id}  will be {record.after_available ? 'enabled' : 'disable'}. Confirmation saves availability only.</label>
        <div className="assistant-actions">
          <button className="button" disabled={busy || !checked || mode !== 'live'} onClick={() => void action((signal) => operate('confirm', signal))}>Confirm crew availability</button>
          <button className="button secondary" disabled={busy || mode !== 'live'} onClick={() => void action((signal) => operate('cancel', signal))}>Cancel availability preview</button>
        </div>
      </>}
      {record.status === 'pending' && expired && <p role="status">This preview expired. Create a new preview.</p>}
      <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => void action(async (signal) => {
        const next = await api.changeRequest(record.change_id, { signal }); if (!signal.aborted) show(next)
      })}>Refresh availability result</button>
      {record.status === 'confirmed' && <>
        <p>Saved input revision {record.applied_revision}. {record.planning_input_changed ? 'The original plan is stale.' : 'The input revision is unchanged.'} {planNames[record.replan_status]}. </p>
        {record.replan_error_code && <p role="alert">{errorMessage(new ApiError(record.replan_error_code, 'Failed', 503, 'http'))} Availability is saved. No successful recalculation result exists for this change yet.</p>}
        {running && <p>Recalculation is running. Refresh first. After interruption, recovery is available after {formatSingaporeTime(record.replan_lease_until!)} . Calculations are never repeated automatically.</p>}
        {record.replan_status !== 'succeeded' && <button className="button" disabled={busy || !!running || mode !== 'live'}
          onClick={() => void action((signal) => operate('replan', signal))}>{record.replan_status === 'not_requested' ? 'Recalculate GA and Greedy from saved availability' : 'Retry or recover recalculation'}</button>}
        {record.result && <><p>New plans use input revision {record.result.input_revision}; {record.result.matrix_is_simulated ? 'Simulated travel' : 'External travel data'}. Reload plans to check their current status.</p>
          {record.result.plans.map((p) => <p key={p.plan_id}>{p.algorithm.toUpperCase()}: <code>{p.plan_id}</code></p>)}
          <Link className="button secondary" to="/comparison" onClick={() => rememberRun(record.result!)}>Compare these plans</Link></>}
        <p>To restore availability, check the current plan and preview the opposite change. Later changes are preserved.</p>
      </>}
      <Link to="/routes">Open routes to check current inputs →</Link>
    </article>}
  </section>
}
