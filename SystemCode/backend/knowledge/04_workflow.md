# 巡检、审核与任务记录

document_id：`rg-kb-workflow`；document_version：`5`；owner：`A`。

<a id="workflow-evidence"></a>
## 记录与人工复核

classification：`confirmed_project_fact`。citation_id：`rg-kb-workflow#workflow-evidence`。

当前 HTTP 巡检记录契约是 `a-workflow-v5`。POST /inspections 的成功响应只含 inspection_id、status、detection、task_id；detection 只含 label、confidence、bbox_xyxy、image_width、image_height，无检测为 null。GET /inspections/{id} 返回下面的完整巡检详情，GET /tasks/{id} 返回任务详情；审核前从巡检详情取得 detection_id 和 record_version。上传重放由 HTTP 200 表示，新建为 201；其响应不再带 replayed/input_revision，规划版本通过任务快照取得。上传显式选择 demo 模式/案例，或不含案例的 real 模式；图片统一解码、EXIF 归正并去 metadata 后保存为 RGB PNG。demo 检测是合成数据；real 使用明确配置且经哈希、八类标签核验的本地模型从图片像素推理，Detection.is_demo=false。业务规则仍属演示假设，故 Inspection/Task.is_demo=true。InspectionRecord 保存原始检测、模式、模型版本/权重哈希、位置、规则过程和 review_history；TaskRecord 保存任务与修改历史。严格解析旧记录的客户端须更新 schema；不可直接用 extra=forbid 的旧 a-dto-v1 DTO 接收完整记录。

启用主建议策略的 real 记录还保存 primary_suggestion：一个供展示/审核的检测 ID、策略版本、阈值、排名分数和竞争目标提示。数据库保留全部原始 detections；HTTP InspectionResponse 最多返回一个框：优先返回 accepted 的 selected_detection_id，否则返回主建议，旧记录无建议时返回最高置信度框。竞争 ID 可能指向内部保留证据。排名分数不是正确概率，不用于自动接受阈值。旧记录缺少该字段时为 null，不重新推理；重启、重试和审核后仍保留初次上传的建议。

无检测保存为 no_detection、没有任务；不代表已证明路面安全。demo 模式任一低置信度保存为 pending_review，全部达标才按演示规则选一个候选自动建任务。real 模式采用用户确认的 single-primary-auto-v1：主框原始 confidence ≥ 配置 confidence_threshold（默认 0.60）自动创建一个任务并保存 accepted；低于阈值 pending_review。auto_acceptance 冻结 policy_version 和 confidence_threshold，Task.history.actor_source=system_confidence_policy，review_history 为空表示未进行人工审核。歧义只是提示，不覆盖该分流。阈值尚未校准成正确概率；旧巡检不补任务、不重新推理。仅 pending_review 可发生新的 confirm/correct/dismiss：confirm 选本记录 detection_id，correct 另提供中央 damage_label，dismiss 不选检测。确认不把原置信度改成 1.0，纠正不覆盖原始模型标签，审核决定单独保留。actor_source=user_declared_unverified，不是认证工程人员签名。

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
