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
  unsupported_change: '仅支持明确启用或停用一支队伍，请按示例输入。',
  change_not_pending: '该调整已关闭或已确认，不能执行此操作。',
  change_not_confirmed: '请先核对预览并确认保存队伍状态。',
  change_replan_busy: '本次重算仍在进行，请先查询结果。',
  change_retry_limit: '该调整的重试次数已达上限，请前往路线页核对。',
  change_attempt_superseded: '该计算已被后续恢复操作替代，请查询最新结果。',
  planning_failed: '规划未完成，请核对当前输入后再手动尝试。',
  crew_unavailable: '该队伍已不在当前配置中，请重新核对。',

  assistant_not_configured: '服务端尚未启用模型，请由维护者完成配置。',
  assistant_configuration_error: '服务端模型配置不正确，请联系维护者。',
  assistant_budget_exceeded: '模型调用次数已达限制或服务忙，请稍后重试或联系维护者。',
  assistant_provider_unavailable: '模型服务暂不可用。本次未返回回答，也未自动重试。',
  assistant_invalid_response: '模型返回的证据未通过校验，本次不展示回答。',
  assistant_context_too_large: '方案或知识超出本次问答大小限制，请缩小问题范围。',
  assistant_evidence_changed: '回答期间方案证据发生变化，请重新核对。',
  assistant_stale_plan: '该方案已过期，请先回路线页核对并重新规划。',
  knowledge_unavailable: '知识资料未通过校验，请由维护者同步知识版本。',

  authentication_required: '登录已失效，请重新登录。',
  forbidden: '当前账号没有此操作权限，请联系调度员。',
  csrf_failed: '登录状态已变化，请刷新页面后重试。',
  route_changed: '调度已更新路线，请刷新工作台后核对。',
  task_unavailable: '记录不存在或已不可访问，请刷新工作台。',
  stale_record_version: '记录已被修改。请刷新并重新检查，再提交新操作。',
  stale_input_revision: '任务或队伍已变化。请刷新输入版本，再重新规划。',
  idempotency_conflict: '此请求标识已用于不同内容。请核对操作并创建新请求。',
  invalid_state: '记录当前状态不允许此操作，请刷新查看。',
  route_plan_not_found: '尚未生成路线方案。',
  not_found: '记录不存在或已不可访问。',
  validation_error: '提交内容不符合接口要求，请检查输入。',
  outside_service_area: '位置超出 Jurong 服务范围。',
  image_too_large: '图片过大，请使用不超过 8 MiB、20 MP 的图片。',
  unsupported_image_type: '请选择 JPEG 或 PNG 图片。',
  unsupported_upload_type: '上传格式不符合要求。',
  detector_unavailable: '真实检测服务暂不可用。',
  detector_inference_failed: '图片推理失败，请稍后重试。',
  travel_matrix_unavailable: '行程数据暂不可用；没有生成新方案。',
  database_unavailable: '数据库暂不可用，请稍后重试。',
  mock_write_unavailable: '当前是只读模拟快照，不能提交业务修改。',
  contract_mismatch: '服务返回格式不符合当前接口约定。',
  invalid_response: '服务未返回有效 JSON。',
  request_timeout: '等待服务超时。',
  network_error: '无法连接服务，请检查连接。',
  request_cancelled: '请求已取消。',
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return '发生未知错误，请稍后重试。'
  const message =
    messages[error.code] ?? `请求失败（${error.code}），请稍后重试。`
  return error.outcomeUnknown
    ? `${message} 操作结果尚不确定，请先核对；不要直接发起新的重复操作。`
    : message
}
