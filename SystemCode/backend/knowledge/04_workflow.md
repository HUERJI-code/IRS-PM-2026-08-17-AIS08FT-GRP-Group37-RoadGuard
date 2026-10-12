# 巡检、审核与任务记录

document_id：`rg-kb-workflow`；document_version：`1`；owner：`A`。

<a id="workflow-evidence"></a>
## 记录与人工复核

classification：`confirmed_project_fact`。citation_id：`rg-kb-workflow#workflow-evidence`。

当前 HTTP 记录契约是 `a-workflow-v1`。上传显式选择 demo 模式/案例，图片只做真实解码和 EXIF 归正、去 metadata 的 RGB PNG 保存，合成检测框按保存图片尺寸缩放；没有从像素识别损坏。InspectionRecord 保存原始检测、来源、位置、规则过程和 review_history；TaskRecord 保存任务与修改历史。额外版本/历史字段不能直接交给 extra=forbid 的旧 a-dto-v1 基础 DTO。

无检测保存为 no_detection、没有任务；任一低置信度保存为 pending_review、没有任务；全部达标按演示规则选一个候选，保存 accepted 并创建一个任务。仅 pending_review 可发生新的 confirm/correct/dismiss：confirm 选本记录 detection_id，correct 另提供中央 damage_label，dismiss 不选检测。确认不把原置信度改成 1.0，纠正不覆盖原始模型标签，审核决定单独保留。actor_source=user_declared_unverified，不是认证工程人员签名。

来源：[src-workflow-service](../roadguard/inspections/service.py)、[src-workflow-schema](../roadguard/schemas/workflow.py)、[src-images-code](../roadguard/images.py)、[context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md)。

<a id="workflow-task-state"></a>
## 任务状态与可修改字段

classification：`confirmed_project_fact`。citation_id：`rg-kb-workflow#workflow-task-state`。

只有 active 任务参加新的规划读取；completed/cancelled 保留历史，不物理删除、不重新激活。活动任务允许完成/取消、纠正 damage_label，或 latitude/longitude/road_type 一起修正。标签纠正由服务端按巡检冻结规则重新计算严重度、优先级、分钟数和建议；位置重新校验范围并保留巡检的原始位置。不接受自由填写 priority/service_minutes/due_at、空修改或显式 null。

任务创建或真正修正/完成/取消会改变规划输入；巡检待复核、无检测、驳回不改变活动任务输入。B 应读取同一快照的 active 任务和共同 input_revision；多页有不同版本时不能拼成同一次规划。四队分配和路线结果由 B 的未来规划服务负责，不从任务记录推导已生成方案。

来源：[src-workflow-service](../roadguard/inspections/service.py)、[src-workflow-schema](../roadguard/schemas/workflow.py)、[context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md)、[context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md)。

<a id="workflow-versions"></a>
## 版本与安全重试

classification：`confirmed_project_fact`。citation_id：`rg-kb-workflow#workflow-versions`。

record_version 是单条资源的乐观并发版本，审核/修改带 expected_version；input_revision 是共同规划输入版本，实际任务变化在同一数据库事务中递增一次。Idempotency-Key 防上传重复，request_id 防对应资源审核/修改重复：相同请求安全重放，内容改变或过期的新操作返回冲突。重放返回当前资源/当前输入版本，不是缓存的旧状态；重试和无业务值变化不重复递增、不重复建任务。

planning_input_changed 只表示此次请求实际改变共同输入，replayed 表示安全重放；它们不表示路线计算成功。C 必须按 code/status 处理错误和冲突并重新读取资源，不能把旧方案或演示响应显示为新的真实结果。

来源：[src-workflow-service](../roadguard/inspections/service.py)、[src-workflow-schema](../roadguard/schemas/workflow.py)、[context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md)。
