import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../api/context'
import { ApiError } from '../api/errors'
import { formatSingaporeTime, stopTime } from '../api/format'
import { ErrorState, LoadingState } from '../components/RequestState'
import { usePlanningRun } from '../planning/runContext'
import { unassignedReasons } from '../map/geography'
import { assessPair, numberText, percentageChange, priorities, type Pair, type Plan } from '../planning/comparison'

type MetricRow = { label: string; unit: string; read: (plan: Plan) => number | null; percent?: boolean; note?: string }
const rows: MetricRow[] = [
  { label: 'Assigned tasks', unit: 'tasks', read: (p) => p.metrics.assigned_task_count },
  { label: 'Unassigned tasks', unit: 'tasks', read: (p) => p.metrics.unassigned_task_count },
  ...priorities.map((priority) => ({ label: `${priority} Unassigned`, unit: 'tasks', read: (p: Plan) => p.metrics.unassigned_by_priority[priority] ?? null })),
  { label: 'Total travel', unit: 'min', read: (p) => p.metrics.total_travel_minutes, percent: true, note: 'Includes depot-to-first-stop travel; return travel follows the saved configuration.' },
  { label: 'Total repair time', unit: 'min', read: (p) => p.metrics.total_service_minutes },
  { label: 'Makespan', unit: 'min', read: (p) => p.metrics.makespan_minutes, percent: true, note: 'From the shared start time until the last available crew finishes, including depot return when configured.' },
  { label: 'Workload standard deviation', unit: 'min', read: (p) => p.metrics.workload_std_minutes, percent: true, note: 'Travel plus repairs for available crews; idle crews count as 0, unavailable crews are excluded.' },
  { label: 'Priority-weighted mean completion time', unit: 'min', read: (p) => p.metrics.priority_weighted_completion_minutes, percent: true, note: 'Backend weighted mean; this is not lateness.' },
  { label: 'Tasks with deadlines', unit: 'tasks', read: (p) => p.metrics.tasks_with_due_at },
  { label: 'Total lateness', unit: 'min', read: (p) => p.metrics.tasks_with_due_at === 0 ? null : p.metrics.total_lateness_minutes, percent: true, note: 'Cannot calculate without deadlines. With deadlines, lateness covers assigned tasks only; also check unassigned tasks.' },
  { label: 'Late tasks', unit: 'tasks', read: (p) => p.metrics.tasks_with_due_at === 0 ? null : p.metrics.late_task_count },
  { label: 'Objective value', unit: 'weighted min', read: (p) => p.metrics.objective_value, percent: true, note: 'The backend compares unassigned P1 / P2 / P3 counts before weighted cost. Do not assess the objective value alone.' },
  { label: 'Algorithm runtime', unit: 'ms', read: (p) => p.metrics.algorithm_runtime_ms, percent: true, note: 'Excludes travel-matrix preparation and external API waiting. This is not repair completion time.' },
]

export default function ComparisonPage() {
  const { api, mode } = useApi()
  const { run } = usePlanningRun()
  const [refresh, setRefresh] = useState(0)
  const [data, setData] = useState<{ pair: Pair; revision: number } | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal }
    async function load() {
      setBusy(true)
      setError(null)
      setData(null)
      try {
        async function read(algorithm: 'ga' | 'greedy') {
          const id = run?.plans.find((p) => p.algorithm === algorithm)?.plan_id
          if (run && !id) throw new ApiError('contract_mismatch', 'Missing pair ID', 0, 'contract')
          try {
            const plan = id ? await api.plan(id, options) : await api.latestPlan(algorithm, options)
            if (plan.algorithm !== algorithm || (id && plan.plan_id !== id)) throw new ApiError('contract_mismatch', 'Wrong plan', 0, 'contract')
            return plan
          } catch (err) {
            if (err instanceof ApiError && err.code === 'route_plan_not_found') return null
            throw err
          }
        }
        const [ga, greedy, health] = await Promise.all([read('ga'), read('greedy'), api.health(options)])
        if (!controller.signal.aborted) setData({ pair: { ga, greedy }, revision: health.input_revision })
      } catch (err) {
        if (!controller.signal.aborted) setError(err)
      } finally {
        if (!controller.signal.aborted) setBusy(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [api, run, refresh])
  const check = data ? assessPair(data.pair, run) : null
  const ga = data?.pair.ga
  const greedy = data?.pair.greedy
  const stale = data && [ga, greedy].some((p) => p && (p.is_stale || p.input_revision !== data.revision))
  return <>
    <div className="page-heading">
      <p className="eyebrow">PLAN COMPARISON / 05</p><h1>Algorithm comparison</h1>
      <p className="description">Compare saved GA and Greedy results. Verify the same run first, then review coverage and metrics.</p>
    </div>
    <div className="map-controls"><button className="button" disabled={busy} onClick={() => setRefresh((n) => n + 1)}>Reload comparison</button><Link className="button secondary" to="/routes">Recalculate in four-crew routes</Link></div>
    {mode !== 'live' && <p className="notice">Read-only mock example; not actual planning or experimental evidence.</p>}
    {busy && <LoadingState />}
    {error !== null && <><ErrorState error={error} /><p>Comparison loading failed; unverified differences are hidden. Retrying only reads plans and does not recalculate.</p></>}
    {data && check && <>
      <section className="notice" aria-label="Comparison basis">
        <h2>{check.comparable ? 'Same-run plans verified' : 'Comparability not verified'}</h2>
        {check.reasons.map((reason) => <p key={reason}>{reason}</p>)}
        {!run && <p>Recalculate in four-crew routes before opening this page to retain same-run evidence. Refreshing or changing sources clears this evidence; matching times or revisions alone cannot restore it.</p>}
        {run && <p>Run input revision {run.input_revision} · Tasks: {run.task_count} · Matrix {run.matrix_provider} · {run.matrix_is_simulated ? 'Simulated travel' : 'External travel data'} · Retrieved {formatSingaporeTime(run.matrix_generated_at)}</p>}
        <p>{stale ? 'The plan is stale and is shown for historical comparison only. Replan the current schedule.' : 'Status reflects this read and does not guarantee that inputs have stayed unchanged.'} Latest input revision:{data.revision}. </p>
        {check.comparable && !check.sameCoverage && <p>The assigned task sets differ. Task-count differences remain available; time and objective values are shown without percentage comparisons.</p>}
      </section>
      {ga && greedy && <div className="comparison-overview" aria-label="Two-plan overview">
        <div><p className="eyebrow">01 / Task coverage</p><h3>Check which tasks are scheduled first</h3><p><strong>GA {ga.metrics.assigned_task_count}</strong><span>Greedy {greedy.metrics.assigned_task_count}</span></p><small>Assigned task counts; see unassigned reasons below.</small></div>
        <div><p className="eyebrow">02 / Travel time</p><h3>Then check crew travel time</h3><p><strong>GA {numberText(ga.metrics.total_travel_minutes)}</strong><span>Greedy {numberText(greedy.metrics.total_travel_minutes)}</span></p><small>Unit: minutes. No percentage comparison when assigned task sets differ.</small></div>
      </div>}
      {ga && greedy && <section className="review-record comparison-panel" aria-label="Metric comparison">
        <h2>Metrics side by side</h2>
        <p className="comparison-mobile-hint">On narrow screens, scroll horizontally to view both algorithms and the change column.</p>
        <p>Percentage change = (GA − Greedy)÷ Greedy; Negative values indicate a decrease; positive values indicate an increase. A decrease in one metric does not establish a better overall result or monetary savings.</p>
        <div className="comparison-scroll" role="region" aria-label="Horizontally scrollable metrics table" tabIndex={0}>
          <table className="comparison-table"><caption>Saved plan metrics and change relative to Greedy</caption><thead><tr><th scope="col">Metric</th><th scope="col">GA</th><th scope="col">Greedy</th><th scope="col">Change</th></tr></thead>
            <tbody>{rows.map((row) => {
              const a = row.read(ga), b = row.read(greedy)
              const showChange = check.comparable && (row.unit === 'tasks' || check.sameCoverage)
              return <tr key={row.label}><th scope="row">{row.label}<small>{row.unit}</small></th><td>{a === null ? 'Not calculable' : numberText(a)}</td><td>{b === null ? 'Not calculable' : numberText(b)}</td><td>{!showChange ? 'Not compared' : row.percent ? percentageChange(a, b) : a === null || b === null ? 'Not calculable' : `${a - b > 0 ? '+' : ''}${numberText(a - b)} ${row.unit}`}</td></tr>
            })}</tbody>
          </table>
        </div>
        <details><summary>Metric definitions and limitations</summary><ul>{rows.filter((r) => r.note).map((r) => <li key={r.label}><strong>{r.label}: </strong>{r.note}</li>)}</ul></details>
        <p>This is a single online result, not a substitute for experiments with multiple random seeds or evidence that GA is always better.</p>
      </section>}
      <div className="comparison-plans">{(['ga', 'greedy'] as const).map((algorithm) => {
        const plan = data.pair[algorithm]
        return <section className="review-record comparison-panel" aria-label={`${algorithm.toUpperCase()} Plan details`} key={algorithm}>
          <h2>{algorithm === 'ga' ? 'GA' : 'Greedy'} Plan</h2>
          {!plan ? <p>No saved plan found. This differs from a valid plan with no tasks.</p> : <PlanDetails plan={plan} />}
        </section>
      })}</div>
    </>}
  </>
}

function PlanDetails({ plan }: { plan: Plan }) {
  const seeded = plan.algorithm_parameters.seed_with_greedy
  return <>
    <p className="record-id">{plan.plan_id}</p>
    <p>Input revision {plan.input_revision} · Planning result · Task source {plan.task_source}</p>
    <p>Travel source:{plan.matrix_provider} ({plan.matrix_is_simulated ? 'Simulated matrix' : 'External travel data'})</p>
    <p>Start:{formatSingaporeTime(plan.planning_start_at)}<br />Latest finish:{stopTime(plan.planning_start_at, plan.metrics.makespan_minutes)}</p>
    {plan.algorithm === 'ga' && <p>{seeded === true ? 'GA + Greedy Initial solution' : seeded === false ? 'GA Greedy initial solution not used' : 'Use of Greedy initial solution not provided'}; Random seed {plan.random_seed ?? 'Not provided'}. Do not mix online settings with historical pure-GA experiments.</p>}
    <p>Return to depot:{plan.settings.return_to_depot ? 'Yes' : 'No'}; Shift:{plan.settings.shift_limit.mode === 'limited' ? `${plan.settings.shift_limit.minutes} min` : 'Explicitly unlimited'}. Saved configuration:{plan.settings.config_version}. </p>
    <h3>Crew workload</h3>
    <ul>{plan.crew_routes.map((route) => <li key={route.crew_id}>{route.crew_id} · {{ assigned: 'Assigned', idle: 'Idle', unavailable: 'Unavailable' }[route.status]} · Tasks: {route.stops.length} · {numberText(route.total_work_minutes)} min</li>)}</ul>
    <h3>Unassigned tasks and reasons</h3>
    {plan.unassigned_tasks.length === 0 ? <p>0 unassigned tasks.</p> : <ul>{plan.unassigned_tasks.map((task) => <li key={task.task_id}><Link to={`/tasks?task=${encodeURIComponent(task.task_id)}`}>{task.task_id}</Link> · {unassignedReasons[task.reason] ?? task.reason}<details><summary>Reason code</summary><code>{task.reason}</code></details></li>)}</ul>}
    <details><summary>Saved objective weights and algorithm parameters</summary><pre>{JSON.stringify({ settings: plan.settings, algorithm_parameters: plan.algorithm_parameters, random_seed: plan.random_seed }, null, 2)}</pre></details>
  </>
}
