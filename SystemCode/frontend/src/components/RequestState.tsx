import { errorMessage } from '../api/errors'

export function LoadingState() {
  return <p role="status" className="request-state">Loading data…</p>
}
export function EmptyState({
  message = 'This list is empty.',
}: {
  message?: string
}) {
  return <p role="status" className="request-state">{message}</p>
}
export function NoPlanState() {
  return <p role="status">No route plan has been generated. An empty task list differs from having no plan.</p>
}
export function ErrorState({ error }: { error: unknown }) {
  return <p role="alert">{errorMessage(error)}</p>
}
