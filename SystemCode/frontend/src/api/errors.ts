export type ErrorKind =
  'http' | 'network' | 'timeout' | 'cancelled' | 'contract'

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly kind: ErrorKind,
    public readonly details: unknown = null,
    public readonly outcomeUnknown = false,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const messages: Record<string, string> = {
  knowledge_index_unavailable: 'The knowledge vector index is missing or outdated. Ask the maintainer to rebuild it.',
  embedding_model_unavailable: 'The local embedding model is unavailable. Ask the maintainer to run knowledge setup.',
  retrieval_configuration_error: 'The retrieval configuration is invalid. Contact the maintainer.',
  retrieval_input_too_long: 'This question exceeds the embedding limit. Please shorten it.',

  task_change_infeasible: 'This change cannot retain all tasks within the shift and travel constraints. Review the details and select another crew.',
  task_not_assigned: 'This task is not assigned in the selected plan. Load the current plan.',
  task_change_not_pending: 'This task change is already closed. Refresh its saved record.',
  task_change_not_confirmed: 'Confirm the task preview before recalculating.',
  unsupported_change: 'Specify enabling or disabling one crew using the example command.',
  change_not_pending: 'This change is closed or already confirmed.',
  change_not_confirmed: 'Review the preview and confirm the crew change first.',
  change_replan_busy: 'Recalculation is still running. Check the saved result.',
  change_retry_limit: 'The retry limit was reached. Check the routes workspace.',
  change_attempt_superseded: 'A recovery attempt replaced this calculation. Check the latest result.',
  planning_failed: 'Planning did not complete. Check current inputs before trying again.',
  crew_unavailable: 'This crew is no longer configured. Refresh and check it.',
  assistant_not_configured: 'The model is not enabled. Ask the maintainer to configure it.',
  assistant_configuration_error: 'The server model configuration is invalid. Contact the maintainer.',
  assistant_budget_exceeded: 'The model call limit was reached or the service is busy.',
  assistant_provider_unavailable: 'The model service is unavailable. No answer or automatic retry was produced.',
  assistant_invalid_response: 'The model evidence failed validation; no answer is displayed.',
  assistant_context_too_large: 'The plan or knowledge exceeds the question size limit. Narrow the question.',
  assistant_evidence_changed: 'The evidence changed while answering. Refresh and check it.',
  assistant_stale_plan: 'This plan is stale. Check the routes workspace and replan.',
  knowledge_unavailable: 'Knowledge validation failed. Ask the maintainer to synchronize the package.',

  authentication_required: 'Your session has expired. Please sign in again.',
  forbidden: 'Your account cannot perform this action. Contact the dispatcher.',
  csrf_failed: 'Your session has changed. Refresh the page and try again.',
  route_changed: 'Dispatch has updated the route. Refresh your workspace and check it.',
  task_unavailable: 'This record is unavailable. Refresh the workspace.',
  stale_record_version: 'The record has changed. Refresh and check it before submitting a new action.',
  stale_input_revision: 'Tasks or crews have changed. Refresh the input revision and replan.',
  idempotency_conflict: 'This request ID was used with different content. Check the action and create a new request.',
  invalid_state: 'The current record status does not allow this action. Refresh to check it.',
  route_plan_not_found: 'No route plan has been generated.',
  not_found: 'The record does not exist or is no longer accessible.',
  validation_error: 'The submission does not meet the API requirements. Check your inputs.',
  outside_service_area: 'The location is outside the Jurong service area.',
  image_too_large: 'The image is too large. Use an image within 8 MiB and 20 MP.',
  unsupported_image_type: 'Select a JPEG or PNG image.',
  unsupported_upload_type: 'The upload format is unsupported.',
  detector_unavailable: 'Real detection is temporarily unavailable.',
  detector_inference_failed: 'Image inference failed. Please try again later.',
  travel_matrix_unavailable: 'Travel data is unavailable; no new plan was generated.',
  database_unavailable: 'The database is temporarily unavailable. Please try again later.',
  mock_write_unavailable: 'This is a read-only mock snapshot. Changes cannot be submitted.',
  contract_mismatch: 'The service response does not match the current API contract.',
  invalid_response: 'The service did not return valid JSON.',
  request_timeout: 'The service request timed out.',
  network_error: 'Cannot connect to the service. Check your connection.',
  request_cancelled: 'The request was cancelled.',
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'An unexpected error occurred. Please try again later.'
  const message =
    messages[error.code] ?? `Request failed (${error.code}), Please try again later.`
  return error.outcomeUnknown
    ? `${message} The outcome is uncertain. Check it before submitting another action.`
    : message
}
