import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../api/context'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { ErrorState, LoadingState } from '../components/RequestState'
import { usePlanningRun } from '../planning/runContext'
import './AssistantPage.css'
import ChangePanel from './ChangePanel'

const classifications: Record<string, string> = {
  confirmed_project_fact: '项目事实',
  demo_assumption: '演示假设',
  pending_decision: '待定事项',
  saved_demo_plan: '保存的演示方案',
}

export default function AssistantPage() {
  const { api, mode } = useApi()
  const { run } = usePlanningRun()
  const [status, setStatus] = useState<Model<'AssistantStatus'> | null>(null)
  const [scope, setScope] = useState<'knowledge' | 'plan'>('knowledge')
  const [question, setQuestion] = useState('')
  const [planId, setPlanId] = useState(run?.plans.find((p) => p.algorithm === 'ga')?.plan_id ?? '')
  const [version, setVersion] = useState('')
  const [result, setResult] = useState<Model<'AssistantAnswer'> | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const request = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    if (mode === 'live') {
      api.assistantStatus({ signal: controller.signal }).then((data) => {
        if (!controller.signal.aborted) setStatus(data)
      }).catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err)
      })
    }
    return () => { controller.abort(); request.current?.abort() }
  }, [api, mode, refresh])

  function clearAnswer() { setResult(null); setError(null); setCancelled(false) }
  async function latest() {
    clearAnswer(); setBusy(true)
    const controller = new AbortController(); request.current = controller
    try {
      const plan = await api.latestPlan('ga', { signal: controller.signal })
      if (!controller.signal.aborted) {
        setPlanId(plan.plan_id)
        if (plan.is_stale) setError(new ApiError('assistant_stale_plan', 'Stale', 409, 'http'))
      }
    } catch (err) { if (!controller.signal.aborted) setError(err) }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  async function ask(event: React.FormEvent) {
    event.preventDefault()
    if (busy || mode !== 'live') return
    clearAnswer(); setBusy(true)
    const controller = new AbortController(); request.current = controller
    try {
      const data = await api.assistantQuery({
        question: question.trim(), scope, plan_id: scope === 'plan' ? planId.trim() : null,
        rule_version: version.trim() || null,
      }, { signal: controller.signal, timeoutMs: 60000 })
      if (!controller.signal.aborted) setResult(data)
    } catch (err) { if (!controller.signal.aborted) setError(err) }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  function cancel() {
    request.current?.abort(); setBusy(false); setResult(null); setCancelled(true)
  }
  return <>
    <div className="page-heading">
      <p className="eyebrow">证据问答 / 07</p>
      <h1>Route assistant</h1>
      <p className="description">核对维修规则，或围绕一份已保存方案查看依据。</p>
    </div>
    <details className="change-section"><summary>队伍调整 · 先预览再确认</summary><ChangePanel /></details>
    <div className="assistant-layout">
      <section className="assistant-question" aria-label="提问">
        <div className="assistant-status"><span className="status-pill">只读问答</span>
          <span>{mode !== 'live' ? '模拟来源 · 问答未启用' : status?.configured ? '模型已配置' : status ? '模型尚未配置' : '正在检查服务'}</span>
        </div>
        <p className="muted">GPT 选择原文证据，回答不修改队伍或任务。模型选择仍可能不完整，请核对引用。</p>
        {mode !== 'live' && <p className="notice">请切换到实时后端后提问；当前模拟样例不会调用模型。</p>}
        {mode === 'live' && status && !status.configured && <p className="notice">服务端尚未启用问答。请由项目维护者配置模型和密钥后重新检查；不要在这里填写密钥。</p>}
        <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => { clearAnswer(); setStatus(null); setRefresh((n) => n + 1) }}>重新检查服务</button>
        <form onSubmit={(event) => void ask(event)}>
          <label htmlFor="assistant-scope">回答依据</label>
          <select id="assistant-scope" value={scope} disabled={busy} onChange={(event) => { setScope(event.target.value as 'knowledge' | 'plan'); clearAnswer() }}>
            <option value="knowledge">项目知识与规则</option><option value="plan">指定路线方案</option>
          </select>
          {scope === 'plan' && <div className="assistant-plan-input">
            <label htmlFor="assistant-plan">方案 ID</label>
            <input id="assistant-plan" value={planId} required pattern="plan-[0-9a-f]{32}" disabled={busy}
              onChange={(event) => { setPlanId(event.target.value); clearAnswer() }} placeholder="从四队路线取得已保存方案" />
            <button type="button" className="text-button" disabled={busy || mode !== 'live'} onClick={() => void latest()}>读取最新 GA 方案 ID</button>
            <small>只读取，不重算。过期方案需要先回路线页核对。</small>
          </div>}
          <label htmlFor="assistant-question">你的问题</label>
          <textarea id="assistant-question" required minLength={2} maxLength={500} rows={5} value={question} disabled={busy}
            onChange={(event) => { setQuestion(event.target.value); clearAnswer() }} placeholder={scope === 'plan' ? '例如：这份方案的总行程是多少？' : '例如：深坑洞的演示维修工时是多少？'} />
          <details><summary>指定规则版本（可选）</summary>
            <label htmlFor="assistant-version">规则版本</label>
            <input id="assistant-version" value={version} maxLength={100} disabled={busy} onChange={(event) => { setVersion(event.target.value); clearAnswer() }} placeholder="例如 demo-rules-v2" />
            <small>旧规则不会被当前规则替代。方案本身未提供每条任务的规则快照。</small>
          </details>
          <div className="assistant-actions">
            <button className="button" disabled={busy || mode !== 'live' || !status?.configured || question.trim().length < 2}>查找依据并回答</button>
            {busy && <button className="button secondary" type="button" onClick={cancel}>停止等待</button>}
          </div>
        </form>
        {status?.configured && <small>每次提交可能产生模型用量。当前进程已尝试 {status.calls_used}/{status.max_calls_per_process} 次（以检查时为准）；失败不自动重试。</small>}
        <Link to="/routes">前往四队路线 →</Link>
      </section>
      <section className="assistant-answer" aria-label="问答结果" aria-busy={busy}>
        {busy && <LoadingState />}
        {cancelled && <p role="status">已停止等待。已发送的模型请求可能仍会完成并产生用量；不会修改业务数据。</p>}
        {error !== null && <ErrorState error={error} />}
        {!busy && !result && !cancelled && error === null && <div className="assistant-empty"><span aria-hidden="true">“</span><h2>让每个回答都有出处</h2><p>提交问题后，查看所选原文、版本和来源。涉及路线数字时，请选择具体方案。</p></div>}
        {result && <>
          <p className="eyebrow">{result.supported ? '已选出引用证据' : '证据不足或暂不可回答'}</p>
          <h2>{result.supported ? '原文依据' : '本次结果'}</h2>
          {result.plan && <p className="notice">方案 {result.plan.plan_id} · 输入版本 {result.plan.input_revision} · {result.plan.algorithm.toUpperCase()} · {result.plan.matrix_is_simulated ? '模拟行程' : '外部行程数据'} · {result.plan.is_stale ? '已过期' : '状态以回答前核对为准'}。维修安排仍为课程演示。</p>}
          {!result.supported && <p role="status">{result.answer}</p>}
          {result.selections.map((item, index) => <article className="assistant-quote" key={`${item.citation_id}-${index}`}>
            <p className="assistant-quote-label">{result.sources.find((source) => source.citation_id === item.citation_id)?.title}</p>
            <pre>{item.quote}</pre>
            <a href={`#assistant-source-${result.sources.findIndex((s) => s.citation_id === item.citation_id)}`}>查看来源 {item.citation_id}</a>
          </article>)}
          {result.sources.length > 0 && <div className="assistant-sources"><h3>引用与版本</h3>
            {result.sources.map((source, index) => <details id={`assistant-source-${index}`} key={source.citation_id}>
              <summary>{source.title} · {classifications[source.classification] ?? source.classification}</summary>
              <p>{source.kind === 'saved_plan' ? '动态方案事实' : '静态知识'} · 版本 {source.version}</p>
              <code>{source.citation_id}</code><pre>{source.content}</pre>
              <small>SHA-256：{source.sha256}</small>
              {source.provenance.map((p) => <p key={p.source_id}><code>{p.path}</code><small>{p.integrity === 'sha256_verified' ? '固定来源摘要已核对' : '可变上下文，未校验摘要'}</small></p>)}
            </details>)}
          </div>}
          <div className="assistant-limits">{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            <small>知识包 {result.package_version} · {result.model_called ? `模型 ${result.model} 已调用` : '未调用模型'} · 未修改业务数据</small>
          </div>
        </>}
      </section>
    </div>
  </>
}
