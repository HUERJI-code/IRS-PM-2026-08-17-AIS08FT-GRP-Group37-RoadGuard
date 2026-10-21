// Metadata is separate from the frozen upload/review JSON contracts.
export function replanningMessage(status: unknown): string | null {
  if (status === 'completed') return 'Automatic GA and Greedy route recalculation completed. Check the latest saved routes.'
  if (status === 'failed') return 'Task saved; automatic route recalculation failed. Dispatcher can retry from Four-crew routes.'
  if (status === 'not_needed') return 'No additional route recalculation was needed for this request. Check the latest saved routes for current assignments.'
  return null
}
