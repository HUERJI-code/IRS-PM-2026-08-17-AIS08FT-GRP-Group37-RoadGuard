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
  pending: '等待确认', confirmed: '队伍状态已保存', cancelled: '已取消', expired: '预览已过期', failed: '确认被拒绝',
}
const planNames: Record<Change['replan_status'], string> = {
  not_requested: '尚未重算', running: '正在重算', failed: '重算失败', succeeded: '新方案已保存',
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
  return <section className="change-panel" aria-label="队伍调整">
    <h2>队伍调整</h2>
    <p>先核对预览，再由你确认。确认只保存队伍可用状态，生成新路线需要另外点击重算。</p>
    <p className="notice">支持“停用 crew-02”“启用 crew-02”或“将 crew-02 设为不可用”。每次仅调整一队；复合指令、封路和自动重算不会被猜测执行。此流程不调用 GPT。</p>
    {mode !== 'live' && <p role="status">模拟来源不允许创建或确认调整，请先切回实时后端。</p>}
    <fieldset disabled={busy || mode !== 'live'} className="change-form">
      <label htmlFor="change-plan">调整依据方案 ID</label>
      <input id="change-plan" value={planId} onChange={(e) => { setPlanId(e.target.value); edit() }} placeholder="已保存且未过期的方案" />
      <button className="text-button" onClick={() => void action(async (signal) => {
        const plan = await api.latestPlan('ga', { signal })
        if (!signal.aborted) {
          edit(); setPlanId(plan.plan_id)
          if (plan.is_stale) throw new ApiError('assistant_stale_plan', 'Stale', 409, 'http')
        }
      })}>读取调整依据方案</button>
      <label htmlFor="change-instruction">调整指令</label>
      <input id="change-instruction" value={instruction} maxLength={200} onChange={(e) => { setInstruction(e.target.value); edit() }} placeholder="停用 crew-02" />
      <button className="button" disabled={!instruction.trim() || !/^plan-[0-9a-f]{32}$/.test(planId.trim())} onClick={() => void action(create)}>生成调整预览</button>
    </fieldset>
    {busy && <p role="status">正在处理，请勿重复提交。离开页面不会撤销已发出的操作。</p>}
    {error !== null && <><ErrorState error={error} /><p>网络中断时，请查询下方已有记录确认结果。重算失败不会自动恢复队伍，也不会自动再试。</p></>}
    <div className="change-recovery">
      <h3>查询与恢复</h3>
      <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => void action(async (signal) => {
        const list = await api.changeRequests({ signal }); if (!signal.aborted) setItems(list.items)
      })}>读取我的最近调整</button>
      {items.length > 0 && <ul>{items.map((item) => <li key={item.change_id}>
        <button className="text-button" disabled={busy} onClick={() => void action(async (signal) => {
          const next = await api.changeRequest(item.change_id, { signal }); if (!signal.aborted) show(next)
        })}>{item.instruction} · {stateNames[item.status]} · {formatSingaporeTime(item.created_at)}</button>
      </li>)}</ul>}
      <label htmlFor="recover-change">按调整 ID 查询</label>
      <input id="recover-change" value={recoveredId} disabled={busy} onChange={(e) => setRecoveredId(e.target.value)} placeholder="change-…" />
      <button className="text-button" disabled={busy || mode !== 'live' || !/^change-[0-9a-f]{32}$/.test(recoveredId.trim())}
        onClick={() => void action(async (signal) => {
          const next = await api.changeRequest(recoveredId.trim(), { signal }); if (!signal.aborted) show(next)
        })}>查询指定调整</button>
    </div>
    {record && <article className="change-preview" aria-label="调整预览与结果">
      <p className="eyebrow">{stateNames[record.status]}</p>
      <h3>{record.crew_id}：{record.before_available ? '可用' : '不可用'} → {record.after_available ? '可用' : '不可用'}</h3>
      <p>预览输入版本 {record.input_revision} · 队伍版本 {record.crew_record_version} · 调整记录版本 {record.record_version}</p>
      <p>调整 ID：<code>{record.change_id}</code></p>
      <p>确认期限：{formatSingaporeTime(record.expires_at)}</p>
      <p>{record.warning}</p>
      {record.before_available === record.after_available && <p>目标状态与预览时相同；确认会留下记录，不额外增加规划输入版本。</p>}
      {record.error_code && <p role="alert">{errorMessage(new ApiError(record.error_code, 'Rejected', 409, 'http'))} 请重新核对当前方案后生成新预览。</p>}
      {record.status === 'pending' && !expired && <>
        <label className="change-check"><input type="checkbox" checked={checked} disabled={busy} onChange={(e) => setChecked(e.target.checked)} />
          我已核对 {record.crew_id} 将{record.after_available ? '启用' : '停用'}，确认只保存队伍状态。</label>
        <div className="assistant-actions">
          <button className="button" disabled={busy || !checked || mode !== 'live'} onClick={() => void action((signal) => operate('confirm', signal))}>确认保存队伍状态</button>
          <button className="button secondary" disabled={busy || mode !== 'live'} onClick={() => void action((signal) => operate('cancel', signal))}>取消此预览</button>
        </div>
      </>}
      {record.status === 'pending' && expired && <p role="status">预览已到期，请生成新预览。</p>}
      <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => void action(async (signal) => {
        const next = await api.changeRequest(record.change_id, { signal }); if (!signal.aborted) show(next)
      })}>刷新此调整结果</button>
      {record.status === 'confirmed' && <>
        <p>已保存输入版本 {record.applied_revision}。{record.planning_input_changed ? '原方案已过期。' : '本次未改变输入版本。'} {planNames[record.replan_status]}。</p>
        {record.replan_error_code && <p role="alert">{errorMessage(new ApiError(record.replan_error_code, 'Failed', 503, 'http'))} 队伍状态已经保存，尚无本次成功重算结果。</p>}
        {running && <p>重算正在执行。先刷新查询；若服务中断，{formatSingaporeTime(record.replan_lease_until!)} 后可显式恢复。不会自动重复计算。</p>}
        {record.replan_status !== 'succeeded' && <button className="button" disabled={busy || !!running || mode !== 'live'}
          onClick={() => void action((signal) => operate('replan', signal))}>{record.replan_status === 'not_requested' ? '按已保存状态重算 GA 与 Greedy' : '重试或恢复重算'}</button>}
        {record.result && <><p>新方案基于输入版本 {record.result.input_revision}；{record.result.matrix_is_simulated ? '模拟行程' : '外部行程数据'}，以重新读取的方案状态为准。</p>
          {record.result.plans.map((p) => <p key={p.plan_id}>{p.algorithm.toUpperCase()}：<code>{p.plan_id}</code></p>)}
          <Link className="button secondary" to="/comparison" onClick={() => rememberRun(record.result!)}>查看本次方案比较</Link></>}
        <p>如需恢复队伍原状态，请先核对当前方案，再创建相反操作的新预览；不会覆盖之后发生的修改。</p>
      </>}
      <Link to="/routes">前往四队路线核对当前输入 →</Link>
    </article>}
  </section>
}
