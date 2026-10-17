import { useState, type ReactNode } from 'react'
import { RunContext, type RunReceipt } from './runContext'

// Only a successful recalculation response establishes a pair. No URL or
// independently fetched latest plan can create a receipt. Source changes remount us.
export default function PlanningRunProvider({ children }: { children: ReactNode }) {
  const [run, rememberRun] = useState<RunReceipt | null>(null)
  return <RunContext.Provider value={{ run, rememberRun }}>{children}</RunContext.Provider>
}
