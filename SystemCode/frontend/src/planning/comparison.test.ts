import { expect, it } from 'vitest'
import fixtures from '../test/planning-fixtures.json'
import { parseModel } from '../api/contracts'
import { assessPair, percentageChange, type Pair, type Plan } from './comparison'

const makePair = (): Pair => ({ ga: parseModel('RoutePlan', structuredClone(fixtures.plans.ga)), greedy: parseModel('RoutePlan', structuredClone(fixtures.plans.greedy)) })
const receipt = () => parseModel('RecalculationResult', structuredClone(fixtures.calculation))
it('accepts an actual backend same-run pair and ignores object key order', () => {
  const pair = makePair()
  pair.greedy!.settings.weights = Object.fromEntries(Object.entries(pair.greedy!.settings.weights).reverse()) as Plan['settings']['weights']
  expect(assessPair(pair, receipt())).toMatchObject({ comparable: true, sameCoverage: true })
})
it('never infers same-matrix provenance from matching latest plans', () => {
  expect(assessPair(makePair(), null).comparable).toBe(false)
})
it.each([
  ['revision', (p: Plan) => { p.input_revision++ }],
  ['start', (p: Plan) => { p.planning_start_at = '2026-10-17T00:00:00Z' }],
  ['source', (p: Plan) => { p.matrix_is_simulated = false }],
  ['provider', (p: Plan) => { p.matrix_provider = 'other' }],
  ['settings', (p: Plan) => { p.settings.return_to_depot = false }],
  ['crew availability', (p: Plan) => { p.crew_routes[0].available = true }],
  ['depot', (p: Plan) => { p.depot.latitude += 0.01 }],
  ['task set', (p: Plan) => { p.crew_routes[1].stops[0].task_id = 'other' }],
  ['counts', (p: Plan) => { p.metrics.assigned_task_count++ }],
  ['duplicate task', (p: Plan) => { p.crew_routes[1].stops.push(p.crew_routes[1].stops[0]) }],
  ['summary objective', (p: Plan) => { p.metrics.objective_value++ }],
  ['wrong id', (p: Plan) => { p.plan_id = 'other' }],
])('blocks comparison after a %s mismatch', (_name, mutate) => {
  const pair = makePair(); mutate(pair.ga!)
  expect(assessPair(pair, receipt()).comparable).toBe(false)
})
it('recognizes differing coverage while retaining same-run evidence', () => {
  const pair = makePair(), run = receipt(), p = pair.ga!
  const stop = p.crew_routes[1].stops.pop()!
  p.unassigned_tasks.push({ task_id: stop.task_id, reason: 'exceeds_shift_limit' })
  p.metrics.assigned_task_count = 0; p.metrics.unassigned_task_count = 1; p.metrics.unassigned_by_priority[stop.priority] = 1
  const summary = run.plans.find((s) => s.algorithm === 'ga')!
  summary.assigned_task_count = 0; summary.unassigned_task_count = 1
  expect(assessPair(pair, run)).toMatchObject({ comparable: true, sameCoverage: false })
})
it('keeps zero distinct from null and handles both directions without claiming improvement', () => {
  expect(percentageChange(0, 5)).toBe('-100%')
  expect(percentageChange(15, 10)).toBe('+50%')
  expect(percentageChange(5, 5)).toBe('0%')
  expect(percentageChange(0, 0)).toContain('基线为 0')
  expect(percentageChange(null, 5)).toBe('无法计算')
})
