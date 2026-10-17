import { createContext, useContext } from 'react'
import type { Model } from '../api/contracts'

export type RunReceipt = Model<'RecalculationResult'>
export const RunContext = createContext<{
  run: RunReceipt | null
  rememberRun: (run: RunReceipt) => void
} | null>(null)

export function usePlanningRun() {
  const value = useContext(RunContext)
  if (!value) throw new Error('PlanningRunProvider is required')
  return value
}
