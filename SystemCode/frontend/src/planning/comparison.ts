import type { Model } from '../api/contracts'
import type { RunReceipt } from './runContext'

export type Plan = Model<'RoutePlan'>
export type Pair = { ga: Plan | null; greedy: Plan | null }
export const priorities = ['P1', 'P2', 'P3'] as const
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value !== null && typeof value === 'object')
    return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(',')}}`
  return JSON.stringify(value)
}
const assignedIds = (plan: Plan) => plan.crew_routes.flatMap((crew) => crew.stops.map((stop) => stop.task_id)).sort()
const allIds = (plan: Plan) => [...assignedIds(plan), ...plan.unassigned_tasks.map((task) => task.task_id)].sort()
const crews = (plan: Plan) => plan.crew_routes.map(({ crew_id, available }) => ({ crew_id, available })).sort((a, b) => a.crew_id.localeCompare(b.crew_id))
const sameTime = (a: string, b: string) => Date.parse(a) === Date.parse(b)

export function assessPair(pair: Pair, run: RunReceipt | null) {
  const { ga, greedy } = pair
  const reasons: string[] = []
  if (!ga || !greedy) return { comparable: false, sameCoverage: false, reasons: ['Complete GA / Greedy plans are missing.'] }
  if (!run) reasons.push('No response evidence from the same recalculation; two latest plans alone do not prove the same matrix was used.')
  if (ga.algorithm !== 'ga' || greedy.algorithm !== 'greedy' || ga.plan_id === greedy.plan_id) reasons.push('Algorithm or plan IDs do not match.')
  if (ga.input_revision !== greedy.input_revision || !sameTime(ga.planning_start_at, greedy.planning_start_at)) reasons.push('Input revisions or start times differ.')
  if (canonical(ga.settings) !== canonical(greedy.settings) || canonical(ga.depot) !== canonical(greedy.depot) || canonical(crews(ga)) !== canonical(crews(greedy))) reasons.push('Planning configuration, depot or crew availability differs.')
  if (ga.task_source !== greedy.task_source || ga.matrix_provider !== greedy.matrix_provider || ga.matrix_is_simulated !== greedy.matrix_is_simulated) reasons.push('Task or travel data sources differ.')
  if (canonical(allIds(ga)) !== canonical(allIds(greedy))) reasons.push('Task sets differ.')
  for (const plan of [ga, greedy]) {
    const ids = allIds(plan)
    if (new Set(ids).size !== ids.length || new Set(plan.crew_routes.map((c) => c.crew_id)).size !== plan.crew_routes.length || plan.metrics.assigned_task_count !== assignedIds(plan).length || plan.metrics.unassigned_task_count !== plan.unassigned_tasks.length || (priorities.some((p) => plan.metrics.unassigned_by_priority[p] === undefined) || priorities.reduce((sum, p) => sum + plan.metrics.unassigned_by_priority[p], 0) !== plan.metrics.unassigned_task_count)) reasons.push(`${plan.algorithm.toUpperCase()} task count or uniqueness is inconsistent.`)
    if (run) {
      const summary = run.plans.find((p) => p.algorithm === plan.algorithm)
      if (run.plans.length !== 2 || run.plans.filter((p) => p.algorithm === plan.algorithm).length !== 1 || !summary || summary.plan_id !== plan.plan_id || summary.assigned_task_count !== plan.metrics.assigned_task_count || summary.unassigned_task_count !== plan.metrics.unassigned_task_count || summary.objective_value !== plan.metrics.objective_value || run.task_count !== ids.length || run.input_revision !== plan.input_revision || !sameTime(run.planning_start_at, plan.planning_start_at) || run.matrix_provider !== plan.matrix_provider || run.matrix_is_simulated !== plan.matrix_is_simulated) reasons.push(`${plan.algorithm.toUpperCase()} does not match this recalculation response.`)
    }
  }
  return { comparable: reasons.length === 0, sameCoverage: canonical(assignedIds(ga)) === canonical(assignedIds(greedy)), reasons }
}

export const numberText = (value: number) => new Intl.NumberFormat('en-SG', { maximumFractionDigits: 2 }).format(value)
export function percentageChange(ga: number | null, greedy: number | null): string {
  if (ga === null || greedy === null) return 'Not calculable'
  if (greedy === 0) return 'Baseline is 0; percentage not calculated'
  const value = (ga - greedy) / greedy * 100
  return `${value > 0 ? '+' : ''}${numberText(value)}%`
}
