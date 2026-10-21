import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../api/context'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { ErrorState, LoadingState } from '../components/RequestState'
import { usePlanningRun } from '../planning/runContext'
import './AssistantPage.css'
import ChangePanel from './ChangePanel'
import TaskAdjustmentPanel from './TaskAdjustmentPanel'

const classifications: Record<string, string> = {
  confirmed_project_fact: 'Project fact',
  demo_assumption: 'Demo assumption',
  pending_decision: 'Pending decision',
  saved_demo_plan: 'Saved demo plan',
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
      <p className="eyebrow">Evidence questions / 07</p>
      <h1>Route assistant</h1>
      <p className="description">Ask about repair rules, saved routes or the configured assistant model. Read the answer, then inspect sources when needed.</p>
    </div>
    <details className="change-section"><summary>Crew adjustments · Preview before confirming</summary><TaskAdjustmentPanel /><details><summary>Crew availability</summary><ChangePanel /></details></details>
    <div className="assistant-layout">
      <section className="assistant-question" aria-label="Question">
        <div className="assistant-status"><span className="status-pill">Read-only questions</span>
          <span>{mode !== 'live' ? 'Mock source · Questions unavailable' : status?.configured ? 'Model configured' : status ? 'Model not configured' : 'Checking service'}</span>
        </div>
        <p className="muted">Answers use project evidence. Select the relevant plan for route questions. Questions do not change crews or tasks.</p>
        {mode !== 'live' && <p className="notice">Switch to the live backend to ask questions. Mock examples do not call the model.</p>}
        {mode === 'live' && status && !status.configured && <p className="notice">Evidence-based answers need an enabled model and server-side key. You can still ask which model is configured or view the assistant's scope. Never enter keys here.</p>}
        <button className="text-button" disabled={busy || mode !== 'live'} onClick={() => { clearAnswer(); setStatus(null); setRefresh((n) => n + 1) }}>Check service again</button>
        <form onSubmit={(event) => void ask(event)}>
          <label htmlFor="assistant-scope">Answer scope</label>
          <select id="assistant-scope" value={scope} disabled={busy} onChange={(event) => { setScope(event.target.value as 'knowledge' | 'plan'); clearAnswer() }}>
            <option value="knowledge">Project knowledge and rules</option><option value="plan">Saved route plan</option>
          </select>
          {scope === 'plan' && <div className="assistant-plan-input">
            <label htmlFor="assistant-plan">Plan ID</label>
            <input id="assistant-plan" value={planId} required pattern="plan-[0-9a-f]{32}" disabled={busy}
              onChange={(event) => { setPlanId(event.target.value); clearAnswer() }} placeholder="Saved plan from the routes workspace" />
            <button type="button" className="text-button" disabled={busy || mode !== 'live'} onClick={() => void latest()}>Read latest GA plan ID</button>
            <small>Read only. Check stale plans in the routes workspace before recalculating.</small>
          </div>}
          <label htmlFor="assistant-question">Your question</label>
          <textarea id="assistant-question" required minLength={2} maxLength={500} rows={5} value={question} disabled={busy}
            onChange={(event) => { setQuestion(event.target.value); clearAnswer() }} placeholder={scope === 'plan' ? 'For example: What is the total travel time in this plan?' : 'For example: What is the demo repair duration for a deep pothole?'} />
          <details><summary>Rule version (optional)</summary>
            <label htmlFor="assistant-version">Rule version</label>
            <input id="assistant-version" value={version} maxLength={100} disabled={busy} onChange={(event) => { setVersion(event.target.value); clearAnswer() }} placeholder="For example demo-rules-v2" />
            <small>Historical rules are preserved. The plan does not include each task rule snapshot.</small>
          </details>
          <div className="assistant-actions">
            <button className="button" disabled={busy || mode !== 'live' || question.trim().length < 2}>Ask assistant</button>
            {busy && <button className="button secondary" type="button" onClick={cancel}>Stop waiting</button>}
          </div>
        </form>
        {status?.configured && <small>Evidence questions may use model quota. Model information and scope guidance do not. This process has attempted {status.calls_used}/{status.max_calls_per_process} calls as of the last check. Failures are not retried automatically.</small>}
        <Link to="/routes">Open four-crew routes →</Link>
      </section>
      <section className="assistant-answer" aria-label="Answer result" aria-busy={busy}>
        {busy && <LoadingState />}
        {cancelled && <p role="status">Stopped waiting. The model request may still complete and use quota. Business data is unchanged.</p>}
        {error !== null && <ErrorState error={error} />}
        {!busy && !result && !cancelled && error === null && <div className="assistant-empty"><span aria-hidden="true">“</span><h2>Ask a specific question</h2><p>A concise answer will appear here. Open View sources for quotations, versions and citations.</p></div>}
        {result && <>
          <p className="eyebrow">{result.answer_mode === 'server_configuration' ? 'Server configuration'
            : result.answer_mode === 'scope_guidance' ? 'Assistant scope'
            : result.supported ? 'Based on selected evidence' : 'Insufficient evidence or unavailable'}</p>
          <h2>{result.answer_mode === 'scope_guidance' ? 'How I can help' : result.supported ? 'Answer' : 'Result'}</h2>
          <div className="assistant-response" role="status">
            {result.answer.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          </div>
          {result.answer_mode !== 'grounded_summary' && <p className="muted">Server response · No model call or retrieval</p>}
          {result.sources.length > 0 && <details className="assistant-source-disclosure">
            <summary>View sources <span>{result.sources.length}  sources</span></summary>
            {result.plan && <p className="notice">Plan {result.plan.plan_id} · Input revision {result.plan.input_revision} · {result.plan.algorithm.toUpperCase()} · {result.plan.matrix_is_simulated ? 'Simulated travel' : 'External travel data'} · {result.plan.is_stale ? 'Stale' : 'Status checked before answering'}. </p>}
            <h3>Source quotations</h3>
            {result.selections.map((item, index) => <article className="assistant-quote" key={`${item.citation_id}-${index}`}>
              <p className="assistant-quote-label">{result.sources.find((source) => source.citation_id === item.citation_id)?.title}</p>
              <pre>{item.quote}</pre>
            </article>)}
            <div className="assistant-sources"><h3>Citations and versions</h3>
              {result.sources.map((source, index) => <details id={`assistant-source-${index}`} key={source.citation_id}>
                <summary>{source.title} · {classifications[source.classification] ?? source.classification}</summary>
                <p>{source.kind === 'saved_plan' ? 'Saved plan facts' : 'Static knowledge'} · Version {source.version}</p>
                <code>{source.citation_id}</code><pre>{source.content}</pre>
                <small>SHA-256: {source.sha256}</small>
                {source.provenance.map((p) => <p key={p.source_id}><code>{p.path}</code><small>{p.integrity === 'sha256_verified' ? 'Pinned source hash verified' : 'Mutable context; hash not verified'}</small></p>)}
              </details>)}
            </div>
            <div className="assistant-limits">{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
              <small>Knowledge package {result.package_version} · {result.model_called ? `Model ${result.model} called` : 'Model not called'}</small>
            </div>
          </details>}
          <p className="assistant-readonly">Read-only answer · Business data unchanged</p>
        </>}
      </section>
    </div>
  </>
}
