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
