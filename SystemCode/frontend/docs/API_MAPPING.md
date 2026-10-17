> 归档说明：下文保留 2026-10-15 规划时的基线与待办，不代表当前全部未实现。第 1–9 步现已实现，实际验证边界见前端 README、VALIDATION.md 和 COMPARISON_GUIDE.md；第 10–14 步尚待实施。

# RoadGuard · C 第 1 步：接口与字段对照表

基线：2026-10-15，main `f8a2cf37de91c09d86ec14e6cbd6045e83e421f8`。A/B 表按当前代码核对，C 表为待冻结设计，不是已经可调用的接口。所有后端地址统一前缀 `/api/v1`；页面编号见《页面流程》。

## 1. 已实现接口（共 17 个）

| 编号/负责人 | 方法与路径（省略统一前缀） | 页面用途 | 请求 | 成功响应与注意事项 |
|---|---|---|---|---|
| H01 A | GET `/health` | 全局连接状态 | 无 | status、database、api_version、input_revision；不表示模型/外部 API 就绪 |
| A01 A | GET `/demo/scenarios` | P1 案例选择 | 无 | is_demo、model_version、image_width/height、scenarios[]（scenario_id、description） |
| A02 A | POST `/inspections` | P1 上传 | multipart image + metadata JSON 字符串；Idempotency-Key 请求头 | 新建 201，重放 200；仅 inspection_id、status、detection、task_id |
| A03 A | GET `/inspections` | P2 列表/P1 历史 | status 默认 all；limit 默认 50，1–100；offset 默认 0 | items:InspectionResponse[]、total、limit、offset；无 input_revision |
| A04 A | GET `/inspections/{inspection_id}` | P1/P2 详情；P3 规则来源 | ID 为 32 位小写十六进制 | InspectionResponse；包含审核所需 detection_id/record_version |
| A05 A | GET `/inspections/{inspection_id}/image` | P1/P2 图片 | 巡检 ID | image/png，no-store；已归一化方向与尺寸 |
| A06 A | POST `/inspections/{inspection_id}/review` | P2 审核 | ReviewRequest，见下表 | inspection、task 可空、input_revision、planning_input_changed、replayed |
| A07 A | GET `/tasks` | P3 列表 | status 默认 active；active/completed/cancelled/all；limit/offset 同上 | items:TaskRecord[]、total、limit、offset、input_revision |
| A08 A | GET `/tasks/snapshot` | 全量活动任务/一致版本读取 | 可选 expected_revision ≥ 0 | contract_version=a-task-query-v1、source=persisted_workflow、tasks:Task[]、total、input_revision、is_demo；不是 TaskRecord[] |
| A09 A | GET `/tasks/{task_id}` | P1 关联任务/P3 详情 | ID 为 32 位小写十六进制 | TaskRecord |
| A10 A | PATCH `/tasks/{task_id}` | P3 编辑/完成/取消 | TaskPatch，见下表 | task、input_revision、planning_input_changed、replayed |
| A11 A | POST `/demo/assessments` | 可选开发预览，非主流程 | scenario_id | is_demo、scenario_id、model_version、image_width/height、confidence_threshold、assessment；不保存巡检或任务 |
| B01 B | GET `/crews` | P4 四队控制 | 无 | contract_version=b-crew-v1、crews:CrewRecord[]、input_revision |
| B02 B | PATCH `/crews/{crew_id}` | P4；未来助手内部服务调用 | request_id、expected_version ≥ 1、available:boolean | contract_version=b-crew-v1、crew、input_revision、planning_input_changed、replayed；不自动重算 |
| B03 B | POST `/route-plans/recalculate` | P4 生成/P5 配对 | expected_revision ≥ 0；可选 planning_start_at（带时区） | 同步 200 RecalculationResult；没有 job、轮询或 request_id |
| B04 B | GET `/route-plans/latest` | P4 最近方案 | algorithm=ga 或 greedy，必填 | RoutePlan；无方案为 404 route_plan_not_found |
| B05 B | GET `/route-plans/{plan_id}` | P4/P5/P6 指定方案 | plan- 加 32 位小写十六进制 | RoutePlan；允许读取旧方案，is_stale 按当前输入版本计算 |

## 2. 写入请求与版本规则

| DTO | 字段 | 约束 |
|---|---|---|
| UploadMetadata | mode、latitude、longitude、road_type；demo 另带 scenario_id | mode real/demo；road_type 仅 public_motor_road；real 必须省略 scenario_id |
| ReviewRequest | request_id、expected_version、action；可选 detection_id、damage_label、note | confirm/correct 必须 detection_id；correct 必须 damage_label；confirm 不允许 damage_label；dismiss 不允许这两项；note ≤ 500 字符 |
| TaskPatch | request_id、expected_version；status、damage_label 或完整位置 | 至少一个非 null 编辑字段；status 仅 completed/cancelled；位置必须同时 latitude/longitude/road_type；无优先级、时长、期限自由编辑 |
| CrewPatch | request_id、expected_version、available | 只修改可用状态；实际无变化不递增输入版本 |
| RecalculateRequest | expected_revision、可选 planning_start_at | 读取和保存时都核对版本；变化则 409，不保存本轮两方案 |

- request_id / Idempotency-Key：1–64 个 ASCII 字母、数字、下划线或连字符。它们标识一次逻辑动作，不是用户身份认证。
- expected_version 是单条记录版本；expected_revision 是全部规划输入的版本，不能互换。
- 数字按数字传递，布尔按布尔传递；未知字段不随意添加。JSON snake_case，ID 字符串。
- 支持幂等的写入发生网络未知结果时复用原 key 与原请求。用户改变内容或处理冲突后是新动作，用新 key。
- 重放可能返回当前资源状态，不能理解为重新创建或再次更新。只有 planning_input_changed 才明确说明本次规划输入发生变化。
- B03 没有幂等保障；重复调用可能生成新方案并重复使用外部服务。

## 3. 页面字段 → 数据来源

| 页面字段/用途 | 真实来源 | 展示规则/缺口 |
|---|---|---|
| 巡检状态/关联任务 | A02.status/task_id；A04.status/task_id | accepted/pending_review/no_detection/rejected；task_id 可空 |
| 上传检测框 | A02.detection.label/confidence/bbox_xyxy/image_width/image_height | detection 可空；无 detection_id，不能直接拿上传回包审核 |
| 审核检测 ID/版本 | A04.detections[].detection_id、record_version | detections 最多一个；primary_suggestion 中其他 ID 不表示可选框 |
| 图片地址 | A04.image_url；A05 | annotated_image_url 可空，不假设有服务端标注图 |
| 模型/业务来源 | A04.mode/model_version/model_weights_sha256/model_manifest_version/is_demo | mode 与业务 is_demo 分开展示；置信度不是准确率 |
| 自动接受/审核记录 | A04.auto_acceptance、review_history、selected_detection_id | 真实主检测达到当前阈值可自动建任务；前端服从返回 status，不自行分流 |
| 标签、严重度、优先级 | A09.damage_label/severity/priority | 来自后端规则，不在前端重算 |
| 时长/期限 | A09.service_minutes/due_at | null 不是 0；分钟；期限缺失不声称逾期 |
| 建议与任务历史 | A09.repair_recommendation/history/created_at/updated_at | 不把 Task.history 当作完整检测决策链 |
| 规则链/版本 | A04.decision_trace；A09.rule_version | 按保存的版本解释历史记录，不用最新规则覆写旧事实 |
| 队伍名称和状态 | B01.crews[].crew_id/name/available/depot_id/record_version/updated_at | updated_at 初始可 null；CrewRecord 没有基地坐标或班次字段 |
| 基地坐标 | B05.depot.depot_id/latitude/longitude | 无方案时需版本化静态地理资料；不是另一个现有 HTTP 接口 |
| 路线状态 | B05.crew_routes[].available/status | assigned/idle/unavailable；不要和 B01 当前队伍状态混淆 |
| 停靠顺序与位置 | B05.crew_routes[].stops[].sequence/task_id/latitude/longitude/priority | 按后端顺序；历史方案不可用当前任务位置覆盖其快照 |
| 到达/完成时间 | stops[].arrival_minute/completion_minute；B05.planning_start_at | UTC 起始时刻加分钟，显示 Asia/Singapore |
| 单段/各队工时 | stops[].travel_minutes_from_previous/service_minutes；crew_routes[].travel_minutes/return_travel_minutes/service_minutes/total_work_minutes/end_minute | return_travel_minutes 可空；按服务端口径展示，避免重复加返程 |
| 路线几何 | crew_routes[].geometry/geometry_note | 当前 geometry=null，仅顺序示意线 |
| 未分配任务 | B05.unassigned_tasks[].task_id/reason | 原因翻译见下表；完整保留，不能丢弃 |
| 约束与来源 | B05.settings、task_source、matrix_provider、matrix_is_simulated、is_demo | 演示工时/模拟行程分别标明；未确认政策不当成正式规定 |
| 方案标识/过期 | B05.plan_id/input_revision/algorithm/is_stale | 单次读取之后也可能过时；写入仍须后端版本检查 |
| 同轮配对/矩阵时间 | B03.plans[]、matrix_generated_at | B05 没有 matrix_generated_at 或 batch_id；保存 B03 回包作本轮上下文 |
| 对比指标 | B05.metrics | 见下表；从保存方案读取，不调用大模型生成数值 |
| 地图边界/标签选择 | Miscellaneous/geography、SystemCode/model/label_schema.json | 没有现成配置/地理 HTTP 接口；交付方式待 D03 对齐 |

TaskRecord 在 Task 的 task_id、inspection_id、latitude、longitude、damage_label、severity、priority、service_minutes、created_at、due_at、status、rule_version、is_demo 上增加 updated_at、record_version、repair_recommendation、history。

RecalculationResult 包含 contract_version=b-recalculation-v1、status=completed、input_revision、planning_start_at、task_count、matrix_provider、matrix_is_simulated、matrix_generated_at、plans；每个 plans 项包含 algorithm、plan_id、assigned_task_count、unassigned_task_count、objective_value。它没有完整 stops，必须再查 B05。

| metrics 字段 | 中文与单位 |
|---|---|
| assigned_task_count / unassigned_task_count / unassigned_by_priority | 分配数量 / 未分配数量 / 按 P1/P2/P3 分组 |
| total_travel_minutes / total_service_minutes | 行程 / 维修总分钟 |
| makespan_minutes | 总完工分钟 |
| workload_std_minutes | 工作量标准差，分钟，可 null |
| priority_weighted_completion_minutes | 优先级加权完成分钟，可 null |
| tasks_with_due_at / total_lateness_minutes / late_task_count | 有期限任务数 / 延误分钟 / 延误任务数；后两项可 null |
| objective_value | 当前目标函数值，结合 settings.objective_version/weights 解读 |
| algorithm_runtime_ms | 算法耗时，毫秒，不代表端到端等待时间 |

| unassigned_tasks.reason | 界面说明 |
|---|---|
| unknown_service_minutes | 维修时长未知 |
| unreachable_from_depot | 从基地不可达 |
| unreachable_to_depot | 无法按当前策略返回基地 |
| no_available_crew | 无可用队伍 |
| exceeds_shift_limit | 超出班次限制 |
| no_feasible_route_position | 无可行的路线插入位置 |

## 4. 正常、空与失败样例

以下是**说明性样例**，不是线上返回或完整 mock 数据集；ID 不可直接查询。完整页面 mock 留到第 3 步按 schema 建立。

正常上传后待审（仅四字段）：

```json
{"inspection_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"pending_review","detection":{"label":"pothole","confidence":0.55,"bbox_xyxy":[10,20,100,120],"image_width":640,"image_height":480},"task_id":null}
```

空检测上传结果：

```json
{"inspection_id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"no_detection","detection":null,"task_id":null}
```

任务空列表（revision 为示意值）：

```json
{"items":[],"total":0,"limit":50,"offset":0,"input_revision":0}
```

确认审核请求（detection_id 必须替换为详情返回值）：

```json
{"request_id":"review_demo_001","expected_version":1,"action":"confirm","detection_id":"from_inspection_detail"}
```

队伍修改与后续重算是两个请求（版本值均为示意）：

```json
{"request_id":"crew_demo_001","expected_version":1,"available":false}
```

```json
{"expected_revision":8,"planning_start_at":"2026-10-15T01:00:00Z"}
```

统一失败结构（提示文本示意，前端只按 code 判断）：

```json
{"code":"stale_input_revision","message":"Planning inputs changed.","details":{}}
```

| 页面/场景 | 正常 | 空或不适用 | 失败处理 |
|---|---|---|---|
| 上传 | accepted → 查任务；pending_review → 审核 | no_detection/detection=null | detector_unavailable 503 / detector_inference_failed 502：显示模型失败，不切 demo |
| 审核 | 返回 inspection/task 与新版本 | 待审 items=[] | stale_record_version 409：重读；invalid_state 409：显示已处理 |
| 任务 | items 有记录 | items=[]；service_minutes=null | not_found 404；outside_service_area 422；保留输入 |
| 队伍 | 四队记录；可用状态保存 | idle 不等于队伍不存在 | stale_record_version / idempotency_conflict 409 |
| 路线 | B03 完成后读取两方案 | route_plan_not_found 404；有效零任务方案仍显示四队 | stale_input_revision 409；travel_matrix_unavailable 503；保留旧方案 |
| 比较 | 同一 B03 配对 | 指标 null；缺少同轮配对证据 | 一边加载失败不显示假差值 |
| 助手 | 拟定：有引用答案/待确认预览 | 拟定：supported=false 或需澄清 | 接口尚未实现，不把 404 当作空答案 |

其他已存在错误包括 validation_error、unsupported_upload_type、unsupported_image_type、invalid_image、image_too_large、image_not_found、image_storage_unavailable、invalid_detection_selection、workflow_unavailable、task_query_unavailable、database_unavailable。具体 details 可按错误提供辅助说明，但不得依赖英文 message 字符串匹配。

## 5. C 助手四接口草案（全部待实现/待冻结）

下面字段是本次建议，不能直接写入“现有 API 类型”。路径来自分工文档，细化字段和状态由 C 提案、A/B 复核。

| 编号 | 方法/路径 | 建议请求 | 建议响应 |
|---|---|---|---|
| C01 | POST `/assistant/query` | question、plan_id；可选 compare_plan_id | plan_id、compare_plan_id 可空、answer、supported、sources[] |
| C02 | POST `/assistant/change-requests` | client_request_id、text、based_on_plan_id | ChangeRequest；无业务写入 |
| C03 | POST `/assistant/change-requests/{id}/confirm` | confirmation_id、expected_request_version | ChangeRequest；原子核验队伍及全局输入版本，执行更新与重算 |
| C04 | POST `/assistant/change-requests/{id}/cancel` | cancellation_id、expected_request_version | ChangeRequest；只允许取消尚未执行请求 |

建议 Explanation.sources 为带 type 的联合结构：

- plan 来源：plan_id、field_path；只引用该保存方案确实存在的值。
- knowledge 来源：document_id、section_id、package_version、document_version、rule_version（不适用时 null）、excerpt。前端显示可定位引用，不接受模型任意构造 URL。
- unsupported 时 supported=false，answer 解释范围；缺少方案返回资源错误，不伪造事实。

建议 ChangeRequest 字段：request_id（服务端资源 ID）、request_version、based_on_plan_id、input_revision、type=crew_availability、params={crew_id,available}、before={available,crew_record_version}、status、created_at、expires_at、business_update_status、recalculation_status、result_plan_id（首选 GA，可空）、result_plan_ids（ga/greedy，可空）、error（可空）。client_request_id 与确认/取消幂等 ID 分开，避免把资源 ID 和每次动作混为一谈。

建议状态机：pending → executing → confirmed；pending → cancelled/expired；executing → failed。failed 必须同时标明业务更新是否成功，不能暗示自动回滚。executing 的重复确认只查询已有执行，不重复修改队伍或重算；已确认后取消应冲突。confirm/cancel 并发由服务端同一请求记录的事务状态转换裁决。

建议错误语义（**未注册，不是当前代码**）：change_request_expired、change_request_conflict、unsupported_change、ambiguous_change、assistant_unavailable；全局过期尽量复用 stale_input_revision。最终 HTTP 状态、details 与错误码由 A 统一登记。

必须解决的确认顺序：

1. 读取确认请求，核验状态和有效期；幂等地认领执行。
2. 在 B 的业务事务内部核对预览 input_revision 与队伍 record_version，再更新队伍；C 不直接写 B 表。
3. 用更新后的 input_revision 调 B 规划服务。
4. 保存执行阶段、新方案 ID 或失败原因；重复确认能够返回该结果。
5. 若队伍已改而重算失败，明确显示部分完成；恢复动作只重试规划，不再次变更队伍。

现有四接口缺少独立的重载查询入口。建议新增只读 GET change-request 状态接口（**额外提案，不计入已约定四个**），或由团队冻结另一种持久恢复协议；不能用页面重载自动调用 confirm 来取状态。当前 B03 也缺执行幂等，因此草案状态机尚不能凭前端单独保证。

## 6. 静态核对依据

仓库根目录：`groupwork1`。以下均为仓库相对路径：

- `AGENTS.md`：所有权、数据单位、首版助手边界。
- `Miscellaneous/TEAM_WORK_ALLOCATION.md`：六类页面、助手四路径；其中旧接口描述以当前代码校正。
- `SystemCode/backend/roadguard/main.py`、`api/health.py`、`api/demo.py`、`api/workflow.py`：挂载与 A 接口。
- `SystemCode/backend/roadguard/schemas/workflow.py`、`schemas/task.py`、`schemas/task_query.py`、`schemas/detection.py`：字段与约束。
- `SystemCode/backend/roadguard/crews/api.py`、`crews/schemas.py`、`crews/service.py`：队伍契约及事务边界。
- `SystemCode/backend/roadguard/routing/api.py`、`routing/models.py`、`routing/service.py`：路线契约、同步重算与同轮保存。
- `SystemCode/backend/roadguard/vision/real.py`：真实检测失败码。
- `SystemCode/backend/knowledge/manifest.json`、`acceptance_cases.json`：知识版本与待修正文案。

本次核对的是静态接口和设计完整性；没有启动服务、运行模型、调用付费 API 或修改业务数据。
