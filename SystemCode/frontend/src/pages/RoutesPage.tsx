import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { usePlanningRun } from '../planning/runContext'
import RouteMap from '../components/RouteMap'
import { useApi } from '../api/context'
import { createOperation, type Operation } from '../api/client'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { formatSingaporeTime } from '../api/format'
import { ErrorState, LoadingState } from '../components/RequestState'
import { crewColor } from '../map/geography'

type CrewOperation = {
  id: string
  operation: Operation<Omit<Model<'CrewPatch'>, 'request_id'>>
}
type Inputs = { crews: Model<'CrewList'>; snapshot: Model<'TaskSnapshot'> }
type Plans = Partial<Record<'ga' | 'greedy', Model<'RoutePlan'> | null>>
const algorithms = ['ga', 'greedy'] as const

export default function RoutesPage() {
  const { api, mode } = useApi()
  const { rememberRun } = usePlanningRun()
  const [mapAlgorithm, setMapAlgorithm] = useState<'ga' | 'greedy'>('ga')
  const [inputs, setInputs] = useState<Inputs | null>(null)
  const [plans, setPlans] = useState<Plans>({})
  const [planError, setPlanError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState('')
  const [ready, setReady] = useState(false)
  const [crewResult, setCrewResult] = useState<Model<'CrewMutation'> | null>(
    null,
  )
  const [calculation, setCalculation] =
    useState<Model<'RecalculationResult'> | null>(null)
  const [pendingCrew, setPendingCrew] = useState<CrewOperation | null>(null)
  const [unknownPlan, setUnknownPlan] = useState(false)
  const [checkedUnknown, setCheckedUnknown] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  const running = useRef(false)
  const mounted = useRef(true)
  const controller = useRef<AbortController | null>(null)

  async function readInputs(signal: AbortSignal, expected?: number) {
    const crews = await api.crews({ signal })
    if (expected !== undefined && crews.input_revision !== expected)
      throw new ApiError('stale_input_revision', 'Input changed', 409, 'http')
    const snapshot = await api.snapshot(crews.input_revision, { signal })
    if (snapshot.input_revision !== crews.input_revision)
      throw new ApiError(
        'contract_mismatch',
        'Inconsistent snapshot',
        0,
        'contract',
      )
    if (mounted.current && !signal.aborted) {
      setInputs({ crews, snapshot })
      setReady(true)
    }
  }
  async function readPlans(signal: AbortSignal) {
    const results = await Promise.allSettled(
      algorithms.map((algorithm) => api.latestPlan(algorithm, { signal })),
    )
    if (!mounted.current || signal.aborted) return false
    let failure: unknown = null
    const next: Plans = {}
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') next[algorithms[index]] = result.value
      else if (
        result.reason instanceof ApiError &&
        result.reason.code === 'route_plan_not_found'
      )
        next[algorithms[index]] = null
      else failure = result.reason
    })
    setPlans((previous) => ({ ...previous, ...next }))
    setPlanError(failure)
    return failure === null
  }
  async function refresh() {
    if (running.current || pendingCrew) return
    running.current = true
    setBusy('Loading inputs and saved plans…')
    setReady(false)
    setError(null)
    controller.current = new AbortController()
    const signal = controller.current.signal
    try {
      await readInputs(signal)
      const checked = await readPlans(signal)
      if (mounted.current && !signal.aborted && unknownPlan) {
        setCheckedUnknown(checked)
        setAcknowledged(false)
      }
    } catch (err) {
      if (mounted.current && !signal.aborted) setError(err)
    } finally {
      if (!signal.aborted) {
        running.current = false
        if (mounted.current) setBusy('')
      }
    }
  }
  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => {
      mounted.current = false
      controller.current?.abort()
      running.current = false
    }
    // Provider remounts on source change; API identity is stable within this page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])
  useEffect(() => {
    if (!busy && !pendingCrew && !unknownPlan) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy, pendingCrew, unknownPlan])

  async function changeCrew(crew: Model<'CrewRecord'>, retry?: CrewOperation) {
    if (
      running.current ||
      mode !== 'live' ||
      unknownPlan ||
      (!retry && (!ready || pendingCrew))
    )
      return
    const change = retry ?? {
      id: crew.crew_id,
      operation: createOperation({
        expected_version: crew.record_version,
        available: !crew.available,
      }),
    }
    running.current = true
    setBusy('Saving crew status…')
    setError(null)
    setReady(false)
    controller.current = new AbortController()
    let saved = false
    try {
      const result = await api.updateCrew(change.id, change.operation, {
        signal: controller.current.signal,
      })
      if (!mounted.current) return
      saved = true
      setCrewResult(result)
      setPendingCrew(null)
      // Preserve the actual saved state even if the subsequent snapshot read fails.
      setInputs((previous) =>
        previous
          ? {
              ...previous,
              crews: {
                ...previous.crews,
                input_revision: result.input_revision,
                crews: previous.crews.crews.map((item) =>
                  item.crew_id === result.crew.crew_id ? result.crew : item,
                ),
              },
            }
          : previous,
      )
      await readInputs(controller.current.signal, result.input_revision)
      await readPlans(controller.current.signal)
    } catch (err) {
      if (!mounted.current) return
      setError(err)
      if (!saved && err instanceof ApiError && err.outcomeUnknown)
        setPendingCrew(change)
      else setPendingCrew(null)
    } finally {
      running.current = false
      if (mounted.current) setBusy('')
    }
  }
  async function recalculate() {
    if (
      running.current ||
      mode !== 'live' ||
      !ready ||
      !inputs ||
      pendingCrew ||
      (unknownPlan && !(checkedUnknown && acknowledged))
    )
      return
    running.current = true
    setBusy('Calculating GA and Greedy…')
    setError(null)
    setCalculation(null)
    setUnknownPlan(false)
    setCheckedUnknown(false)
    setAcknowledged(false)
    controller.current = new AbortController()
    try {
      const result = await api.recalculate(
        { expected_revision: inputs.snapshot.input_revision },
        { signal: controller.current.signal, timeoutMs: 120000 },
      )
      if (!mounted.current) return
      if (
        result.plans.length !== 2 ||
        algorithms.some(
          (algorithm) =>
            result.plans.filter((plan) => plan.algorithm === algorithm)
              .length !== 1,
        ) ||
        result.input_revision !== inputs.snapshot.input_revision
      )
        throw new ApiError(
          'contract_mismatch',
          'Invalid calculation pair',
          0,
          'contract',
          null,
          true,
        )
      setCalculation(result)
      rememberRun(result)
      // The successful response is authoritative; failure reading its plans must not POST again.
      const reads = await Promise.allSettled(
        result.plans.map((plan) =>
          api.plan(plan.plan_id, { signal: controller.current!.signal }),
        ),
      )
      if (!mounted.current) return
      let failure: unknown = null
      reads.forEach((read, index) => {
        if (
          read.status === 'fulfilled' &&
          read.value.plan_id === result.plans[index].plan_id &&
          read.value.input_revision === result.input_revision &&
          read.value.algorithm === result.plans[index].algorithm
        )
          setPlans((previous) => ({
            ...previous,
            [read.value.algorithm]: read.value,
          }))
        else
          failure =
            read.status === 'rejected'
              ? read.reason
              : new ApiError(
                  'contract_mismatch',
                  'Plan mismatch',
                  0,
                  'contract',
                )
      })
      setPlanError(failure)
    } catch (err) {
      if (!mounted.current) return
      setError(err)
      if (
        err instanceof ApiError &&
        err.outcomeUnknown &&
        err.code !== 'travel_matrix_unavailable'
      )
        setUnknownPlan(true)
      if (err instanceof ApiError && err.code === 'stale_input_revision')
        setReady(false)
    } finally {
      running.current = false
      if (mounted.current) setBusy('')
    }
  }
  const locked = !!busy || !!pendingCrew || unknownPlan
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">DISPATCH / 04</p>
        <h1>Four-crew routes</h1>
        <p className="description">
          Accepted new tasks trigger automatic GA and Greedy route recalculation. View the latest saved routes here. Use manual recalculation to retry a failure or after crew, completion or cancellation changes.
        </p>
      </div>
      <nav className="section-links" aria-label="Dispatch page sections"><a href="#dispatch-map">View route map ↓</a><a href="#dispatch-controls">Crews and recalculation ↓</a></nav>
      <div className="dispatch-board">
      <div className="dispatch-controls" id="dispatch-controls" tabIndex={-1}>
      {mode !== 'live' && (
        <p className="notice">This is a read-only mock snapshot. Crew changes and recalculation are unavailable.</p>
      )}
      <button
        className="button"
        disabled={!!busy || !!pendingCrew}
        onClick={() => void refresh()}
      >
        {unknownPlan ? 'Check inputs and saved plans' : 'Refresh inputs and plans'}
      </button>
      {!!busy && <p role="status">{busy}</p>}
      {!inputs && !error && <LoadingState />}
      {error !== null && <ErrorState error={error} />}
      {!ready && inputs && (
        <p className="notice">
          Inputs have not been rechecked. Refresh and check before making changes or recalculating.
        </p>
      )}
      {inputs && (
        <div className="planning-console">
          <section className="review-queue crew-management" aria-label="Crew management">
            <h2>Crew availability</h2>
            <p>
              Configured crews: {inputs.crews.crews.length}{' '}
              . Unavailable crews remain visible; availability does not imply assignment.
            </p>
            <ul className="crew-grid">
              {inputs.crews.crews.map((crew, index) => (
                <li key={crew.crew_id} className={`crew-card ${crew.available ? '' : 'crew-unavailable'}`} style={{ '--crew': crewColor(crew.crew_id) } as CSSProperties}>
                  <span className="crew-avatar" aria-hidden="true">0{index + 1}</span>
                  <strong>
                    {crew.name}
                  </strong>
                  <span className={`status-badge ${crew.available ? 'status-ready' : ''}`}>{crew.available ? 'Available' : 'Unavailable'}</span>
                  <details><summary>Crew record</summary><p>{crew.crew_id} · Record version {crew.record_version} · Depot {crew.depot_id}</p><p>
                    Updated:
                    {crew.updated_at
                      ? formatSingaporeTime(crew.updated_at)
                      : 'Initial configured state'}
                  </p></details>
                  <button
                    disabled={locked || !ready || mode !== 'live'}
                    onClick={() => void changeCrew(crew)}
                  >
                    {crew.available ? 'Disable' : 'Enable'} {crew.name}
                  </button>
                </li>
              ))}
            </ul>
          </section>
          <section className="review-record planning-control" aria-label="Recalculation controls">
            <h2>Check planning inputs</h2>
            <p className="planning-task-count">
              Active tasks: {inputs.snapshot.total} · Input revision{' '}
              {inputs.snapshot.input_revision}
            </p>
            <p className="field-note">
              Source:{inputs.snapshot.source}. Completed and cancelled tasks are excluded from this snapshot.
            </p>
            <details>
              <summary>View active tasks for this run</summary>
              <ul>
                {inputs.snapshot.tasks.map((task) => (
                  <li key={task.task_id}>
                    <Link to={`/tasks?task=${task.task_id}`}>
                      {task.task_id}
                    </Link>{' '}
                    · {task.priority}
                  </li>
                ))}
              </ul>
            </details>
            <p className="field-note">
              The backend sets the start time when calculation begins. GA and Greedy
              use the same inputs and matrix. The matrix source follows backend configuration. Google
              service failures never switch to a simulated matrix. Automatic runs update saved routes; use this manual button to retain the same-run response evidence required by algorithm comparison.
            </p>
            <button
              className="button"
              disabled={
                !!busy ||
                !ready ||
                !!pendingCrew ||
                mode !== 'live' ||
                (unknownPlan && !(checkedUnknown && acknowledged))
              }
              onClick={() => void recalculate()}
            >
              Recalculate GA and Greedy
            </button>
          </section>
        </div>
      )}
      {crewResult && (
        <section className="notice" aria-label="Crew save result">
          <h3>
            {crewResult.replayed ? 'Crew change result recovered' : 'Crew status saved'}
          </h3>
          <p>
            {crewResult.crew.name}:
            {crewResult.crew.available ? 'Available' : 'Unavailable'} · Input revision at save{' '}
            {crewResult.input_revision}
          </p>
          <p>
            Saving crew status does not establish successful recalculation. Check saved plans against current inputs; retrying recalculation does not save the crew again.
          </p>
        </section>
      )}
      {pendingCrew && (
        <section className="notice">
          <p>
            The crew save outcome is unknown. Stay here and retry the original request. Do not change sources or refresh; the retry ID is held in memory only.
          </p>
          <button
            disabled={!!busy}
            onClick={() => {
              const crew = inputs?.crews.crews.find(
                (item) => item.crew_id === pendingCrew.id,
              )
              if (crew) void changeCrew(crew, pendingCrew)
            }}
          >
            Retry crew change with original request
          </button>
        </section>
      )}
      {unknownPlan && (
        <section className="notice">
          <h3>Recalculation outcome uncertain</h3>
          <p>
            The backend may still be calculating or may have saved results. Check inputs and saved plans first; latest plans alone cannot identify this request. This endpoint has no idempotent recalculation ID and does not retry automatically.
          </p>
          {checkedUnknown && (
            <label>
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              I have checked and want to start a new calculation (may duplicate work)
            </label>
          )}
        </section>
      )}
      {calculation && (
        <section className="notice" aria-label="Recalculation result">
          <h2>Recalculation completed</h2>
          <p>
            Input revision {calculation.input_revision} · Task{' '}
            Tasks: {calculation.task_count} ·{' '}
            {formatSingaporeTime(calculation.planning_start_at)}
          </p>
          <p>
            Travel source:{calculation.matrix_provider} (
            {calculation.matrix_is_simulated ? 'Simulated matrix' : 'External travel data'}
            ), Data timestamp {formatSingaporeTime(calculation.matrix_generated_at)}
          </p>
          <ul>
            {calculation.plans.map((plan) => (
              <li key={plan.plan_id}>
                {plan.algorithm.toUpperCase()} · {plan.plan_id} · Assigned{' '}
                {plan.assigned_task_count} / Unassigned {plan.unassigned_task_count}
              </li>
            ))}
          </ul>
          <p>
            These two plan IDs come from the same recalculation response. Later input changes may still make them stale.
          </p>
          <Link className="button" to="/comparison">Compare this GA and Greedy run</Link>
        </section>
      )}
      </div>
      <div className="dispatch-map" id="dispatch-map" tabIndex={-1}>
      <div className="map-controls">
        <label htmlFor="map-algorithm">Map plan</label>
        <select
          id="map-algorithm"
          value={mapAlgorithm}
          onChange={(event) =>
            setMapAlgorithm(event.target.value as 'ga' | 'greedy')
          }
        >
          <option value="ga">GA</option>
          <option value="greedy">Greedy</option>
        </select>
      </div>
      <RouteMap
        key={plans[mapAlgorithm]?.plan_id ?? mapAlgorithm}
        plan={plans[mapAlgorithm]}
        snapshot={inputs?.snapshot}
        currentRevision={inputs?.crews.input_revision}
        readFailed={planError !== null}
      />
      </div>
      </div>
      <section className="review-record" aria-label="Saved plans">
        <h2>Saved plan snapshots</h2>
        {planError !== null && (
          <>
            <ErrorState error={planError} />
            <p>
              Plan loading failed. Retained results have not been revalidated. Refresh the query instead of repeating the calculation.
            </p>
          </>
        )}
        <details className="saved-plans-details"><summary>Expand GA / Greedy plan IDs, status and unassigned reasons</summary>
        <div className="comparison-plans">
        {algorithms.map((algorithm) => {
          const plan = plans[algorithm]
          return (
            <section key={algorithm}>
              <h3>{algorithm.toUpperCase()}</h3>
              {plan === undefined ? (
                <p>Not successfully loaded yet.</p>
              ) : plan === null ? (
                <p>No plan generated (different from an empty-task plan).</p>
              ) : (
                <>
                  <p className="record-id">
                    {plan.plan_id} · Input revision {plan.input_revision}
                  </p>
                  <p>
                    {plan.is_stale ||
                    (inputs &&
                      plan.input_revision !== inputs.crews.input_revision)
                      ? 'The plan is stale and requires replanning.'
                      : 'This plan matches the latest read input revision; this is not a real-time guarantee.'}
                  </p>
                  <p>
                    Travel source {plan.matrix_provider} ·{' '}
                    {plan.matrix_is_simulated ? 'Simulated matrix' : 'External travel data'}
                  </p>
                  <ul>
                    {plan.crew_routes.map((route) => (
                      <li key={route.crew_id}>
                        {route.crew_id}:{' '}
                        {
                          {
                            assigned: 'Assigned',
                            idle: 'Idle',
                            unavailable: 'Unavailable',
                          }[route.status]
                        }{' '}
                        · Tasks: {route.stops.length}
                      </li>
                    ))}
                  </ul>
                  <p>Unassigned tasks: {plan.unassigned_tasks.length}</p>
                  <ul>
                    {plan.unassigned_tasks.map((task) => (
                      <li key={task.task_id}>
                        {task.task_id}: {task.reason}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )
        })}
        </div>
        </details>
      </section>
    </>
  )
}
