# A 公共数据与演示 API 契约

版本：`a-dto-v1`；日期：2026-10-12；维护人：A。此文件是已落实的 A 公共 DTO 契约唯一维护位置。分工表第 6、7 节保留成员职责与未来接口设计，涉及已落实的字段定义应链接本文件；B/C 后续对象由对应负责人提出，不从本文件推定其已冻结。可执行来源为 [schemas](../SystemCode/backend/roadguard/schemas/)，固定样例为 [contracts](../SystemCode/contracts/README.md)。变更必须同时更新 DTO、样例、必要测试与调用方影响说明。

本次冻结数据表示和最低一致性验证，不等于完成 M0：置信度阈值、标签与业务规则映射、多检测选取策略、维修时长、期限和调度参数仍待确认。严禁把样例升级为批准规则。公共导入为 `from roadguard.schemas import Detection, Inspection, Task, ErrorResponse, HealthResponse, PlanningRevision`；另提供结构化 `DecisionTrace`。

第 5 步增量契约为 `a-demo-v1`，保留上述 DTO 字段兼容性，新增 `RuleCandidate`、`RuleAssessment` 和 `/demo` 演示接口。实际演示策略见[规则说明](DEMO_DETECTION_AND_RULES.md)；已实现演示映射不表示正式阈值、工时和优先级获得批准。

第 6 步增量为 `a-workflow-v1`，实现上传、巡检、审核和任务接口，详情见[完整流程与请求样例](INSPECTION_REVIEW_TASK_WORKFLOW.md)。使用新增记录/请求模型，原固定 DTO 样例继续保持兼容。所有在线业务记录仍明确标记演示；道路类型由调用者声明，不代表道路资格核验。

第 7 步增量为 `a-task-query-v1`，提供 B/C 使用的一致活动任务快照；完整使用方式、固定输入、知识包及 HTTP 示例见 [B/C 交接说明](BC_HANDOFF.md)。没有改变原 Task 或 TaskRecord 的字段，也没有冻结 B 的完整 PlanningInput。

## 通用表示

- JSON 字段使用 `snake_case`；ID 与版本用非空字符串，前后空白被去除，纯空白无效。未知字段拒绝，防止调用方静默拼错字段。
- 数值只接受 JSON 数字，不接受字符串或布尔值；整数（类编号、图像尺寸、输入版本）拒绝小数。浮点数必须有限。`is_demo` 只接受布尔值并且显式提供。
- 坐标为 WGS84 十进制度：`latitude` [-90,90]，`longitude` [-180,180]。DTO 只做数值校验；第 6 步业务服务另做冻结 JE/JW 多边形 covers 校验及道路类型声明检查，不把多边形内位置自动判为合格道路。
- 时间戳必须带时区，输入为 ISO 8601 字符串或 Python aware datetime，拒绝无时区时间及 Unix 数字时间戳；归一化 UTC 输出。前端按 `Asia/Singapore` 显示。时长为分钟。
- 下表标为 nullable 的业务字段仍必须提供，未知时传 `null`；`ErrorResponse.details` 可以省略（默认 null），`HealthResponse.api_version` 可以省略（默认 v1）。空列表、null、零有不同含义。
- DTO 约束在构造/解析时验证；它们是传输快照，不是管理业务状态的可变实体。直接赋值、修改内嵌列表或未经验证的 `model_copy(update=...)` 不保证约束仍成立；生产者调整快照后应重新执行 `model_validate`（传 dict）或 `model_validate_json`，状态变更仍由业务服务控制。

## 已冻结对象

| 对象 | 字段与约束 |
| --- | --- |
| Detection | `detection_id`；`class_id` 整数 0～7；`label` 为中央 `label_key`，必须匹配 class_id；`confidence` [0,1]；`bbox_xyxy` 为四个原图像素数值 [left,top,right,bottom]；`image_width/image_height` 为正整数；`model_version`；`is_demo` |
| Inspection | `inspection_id`；`image_url` 非空资源地址（允许相对路径，不保证资源存在）；`annotated_image_url` nullable；坐标；`detections` Detection 列表；`selected_detection_id` nullable；`status`；`task_id` nullable；`decision_trace` DecisionTrace 列表；`is_demo` |
| DecisionTrace | `code` 非空稳定机器标识；`message` 非空说明；`rule_version` nullable（尚未调用规则时为 null）；`is_demo`。列表顺序为决策步骤顺序；没有执行步骤可为空。code 尚不限制业务枚举，不能仅凭 message 判断状态 |
| Task | `task_id`；`inspection_id`；坐标；`damage_label` 中央 label_key；`severity` low/medium/high；`priority` P1/P2/P3；`service_minutes` 正数或 null；`created_at`；`due_at` nullable；`status` active/completed/cancelled；`rule_version`；`is_demo` |
| PlanningRevision | `input_revision` 非负整数；任务/队伍对共同输入的更新语义由共享数据库/服务维护，本 DTO 本身不更新版本 |
| HealthResponse | `status: "ok"`；`database: "ok"`；`api_version: "v1"`；`input_revision` 非负整数。仅表示本次应用与数据库检查成功，不表示模型、Google 或 GPT 就绪 |
| ErrorResponse | `code`、`message` 非空字符串；`details` nullable JSON object/array。嵌套值限有限 JSON 值、对象键限字符串。生产者只放脱敏的错误数量/字段标识等 metadata；不放密码、凭据、原始输入、栈、SQL、内部路径或异常字符串。DTO 不能自动判断文字是否含秘密 |

标签唯一来源为 [label_schema.json](../SystemCode/model/label_schema.json)，Python 通过源码相对路径加载并验证恰好八个不同的 0～7 类。部署必须同时保留此文件，不维护第二套类表。bbox 必须满足 `0 <= left < right <= image_width` 与 `0 <= top < bottom <= image_height`，允许右/下边界等于原图尺寸；框不是归一化 YOLO xywh。

`severity` 的 low/medium/high 只是这版 DTO 词汇选择，不代表从数据集 wide/sunken/deep 推导工程严重度。Task 不提供自由修改优先级的请求 DTO，也不实现标签到 priority/service_minutes/due_at 的映射；未知时长用 null，不用 0。DTO 不根据状态擅自修改队列或创建任务。

Inspection 内 detection_id 必须唯一；非空 selected_detection_id 必须指向本巡检的检测。`no_detection` 必须没有检测、选中对象和任务；其余状态必须有检测。`pending_review` / `rejected` 无 task_id，选中对象允许为空；`accepted` 必须有选中对象和 task_id。含演示检测或演示 trace 的巡检必须标为 is_demo=true；各步骤保留实际来源。DTO 检查快照内关联；第 6 步服务与数据库约束进一步维护跨对象关联、防重复创建、合法状态转换和事务一致性。

## 路由实现状态与错误

当前实现 `GET /api/v1/health`、下列 stateless `/demo` 接口，以及 a-workflow-v1 的巡检上传/查询/图片/审核和任务查询/修改。队伍、规划与助手仍待 B/C 实现。OpenAPI 只展示已注册路由，不用固定样例冒充业务成功。

### a-demo-v1：检测与规则预览

公共类型从 `roadguard.schemas` 导入，定义在 [assessment.py](../SystemCode/backend/roadguard/schemas/assessment.py)；HTTP 包装类型在 [demo.py](../SystemCode/backend/roadguard/api/demo.py)。

| 对象 | 字段与约束 |
| --- | --- |
| RuleCandidate | `detection_id`、中央 `damage_label`、`severity` low/medium/high、`priority` P1/P2/P3、正数或 null 的 `service_minutes`、非空 `repair_recommendation`、`rule_version`、`is_demo: true`。没有 task_id、位置或创建时间，不是 Task |
| RuleAssessment | `status` no_detection/pending_review/ready_for_task、`detections`、nullable `selected_detection_id`、nullable `candidate`、非空 `decision_trace`、`rule_version`、`is_demo: true` |
| DemoAssessmentRequest | 仅 `scenario_id` 非空字符串，最多 64 字符；拒绝额外字段；不接受图片、阈值覆盖或修改业务参数的请求字段 |
| DemoAssessmentResponse | `is_demo: true`、`scenario_id`、`model_version`、`image_width`、`image_height`、实际 `confidence_threshold` 和嵌套 `assessment: RuleAssessment` |
| DemoScenarioCatalogue | `is_demo: true`、`model_version`、`image_width`、`image_height`、`scenarios` 列表，每项 `scenario_id` 与 `description` |

RuleAssessment 内检测 ID 唯一且原图尺寸一致；no_detection 必须无检测；另外两个状态必须有检测。只有 ready_for_task 可有候选，候选必须关联选中的检测、标签和同一规则版本；其他状态的 candidate/selected_detection_id 均为 null。所有 trace 显式标为演示且匹配 assessment 的规则版本。输入真实检测与演示规则混合时，检测保留真实来源标记，assessment/candidate 仍必须标为演示。

`GET /api/v1/demo/scenarios` 返回 DemoScenarioCatalogue；`POST /api/v1/demo/assessments` 接收 DemoAssessmentRequest，200 返回 DemoAssessmentResponse。调用示例 `{"scenario_id":"high_confidence"}`。预览调用只执行服务，不存储巡检/任务、不递增 input_revision，重复请求不会产生队列记录。候选中不含期限，不能计算逾期指标；持久化任务通过第 6 步接口创建，由业务服务执行位置验证、审核分流、存储和幂等性检查。

### a-workflow-v1：持久化业务接口

可执行类型位于 [schemas/workflow.py](../SystemCode/backend/roadguard/schemas/workflow.py)，路由位于 [api/workflow.py](../SystemCode/backend/roadguard/api/workflow.py)。字段和操作说明以[第 6 步指南](INSPECTION_REVIEW_TASK_WORKFLOW.md)及 schema 为准。

| 类型 | 相对基础 DTO 的增量 |
| --- | --- |
| UploadMetadata | 必填 mode=demo、scenario_id、严格数值坐标、road_type=public_motor_road；multipart metadata 字符串的 JSON 内容 |
| InspectionRecord | Inspection 加 created_at、updated_at、record_version、mode、demo_scenario_id、model_version、image_width/height、scope_version、road_type、road_type_source、review_history；强制 is_demo=true |
| TaskRecord | Task 加 updated_at、record_version、repair_recommendation、history；强制 is_demo=true |
| ReviewRequest | request_id、expected_version、action；confirm/correct 必须选 detection_id，correct 必须给 damage_label；dismiss 禁止这些字段；可选 note |
| TaskPatch | request_id、expected_version；至少一个实际修改字段；允许 completed/cancelled、damage_label，或完整 latitude/longitude/road_type；不能直接指定优先级、工时、期限 |
| InspectionMutation | inspection、nullable task、input_revision、planning_input_changed、replayed |
| TaskMutation | task、input_revision、planning_input_changed、replayed |
| InspectionList / TaskList | items、total、limit、offset；TaskList 额外返回同一快照的 input_revision |

Inspection/Task 基础 DTO 的 extra=forbid 不接受新增记录字段，HTTP 调用方须采用相应 Record 类型。原检测标签/置信度保留；人工纠正由 review_history 和 Task.history 表达。review_history 中操作员身份未经认证，不能被当作身份凭据。候选变成任务时才通过事务更新规划版本，单独 `/demo` 调用仍不写库。

### a-task-query-v1：同版本活动任务快照

`GET /api/v1/tasks/snapshot` 返回 `TaskSnapshot`；可选查询参数 expected_revision 为非负整数，不匹配返回 409 stale_input_revision。此固定路径先于 `/tasks/{task_id}` 注册，不会被解释为任务 ID。

可执行定义为 [schemas/task_query.py](../SystemCode/backend/roadguard/schemas/task_query.py)，公共导入为 `from roadguard.schemas import TaskSnapshot`。字段：contract_version 固定 a-task-query-v1；source 为 persisted_workflow 或 synthetic_fixture；input_revision 非负整数；tasks 为原 Task 精确字段列表；total 等于列表长度；is_demo 必须 true。任务均为 active 且 is_demo=true，task_id/inspection_id 不重复。当前不接受真实模型任务，不暗示生产规则已经确认。

在线服务使用 persisted_workflow，读取全部任务、校验存储一致性后返回 active 投影；排序为 created_at、task_id，不截断或分页。损坏的持久化任务导致整次查询 503，不静默返回部分数据。空列表仍为有效 200。查询不改变数据库或 input_revision，未知 service_minutes/due_at 保持 null。

内部服务 `from roadguard.tasks import TaskQueryService`，签名 `snapshot(expected_revision=None, *, connection=None)`。默认自行管理只读事务；提供 connection 时要求同一数据库已存在的事务，服务不提交/回滚/关闭它。任务与版本来自同一读取快照。B 将来应在同连接读取队伍，并在保存计算结果的写事务中再次核对版本；HTTP 任务快照不保证其他 HTTP 查询的队伍同版本。

固定文件的 source=synthetic_fixture、版本号仅为离线样例上下文，不是在线数据库状态。知识包另有自身文档版本；规则说明必须匹配任务保存的 rule_version。

### 统一错误

统一错误的可执行来源为 [errors.py](../SystemCode/backend/roadguard/errors.py) 及 [health.py](../SystemCode/backend/roadguard/api/health.py)；使用 `code` 判断，不匹配 message 文本。当前错误码如下，变更须与实现同步：

| code | HTTP 状态 | 当前含义 |
| --- | --- | --- |
| `validation_error` | 422 | FastAPI 请求校验失败，details 仅 error_count，不回显原始输入 |
| `not_found` | 404 | 路径、巡检或任务不存在 |
| `method_not_allowed` | 405 | 已有路径不支持该方法，保留 Allow header |
| `stale_input_revision` | 409 | 共享数据库或任务快照拒绝旧预期版本；details 含 expected_revision/current_revision；仍无规划 HTTP handler |
| `database_unavailable` | 503 | 数据库不可用、基础状态无效或持久化记录无法解析 |
| `internal_error` | 500 | 未处理异常的安全公共说明，无原始异常文字 |
| `http_error` | 对应 HTTP 状态 | 其他 HTTPException 的通用安全说明 |
| `demo_scenario_not_found` | 404 | 未知的固定演示案例，不回显传入值 |
| `demo_unavailable` | 503 | 演示服务未就绪，不用成功样例替代错误 |
| `invalid_detections` | 422 | 规则服务收到非法检测快照；属于内部服务入口校验，HTTP 演示请求不能自行传入检测 |
| `outside_service_area` | 422 | 任务点在冻结 JE/JW 多边形范围外；NUS-ISS 不获得任务例外 |
| `unsupported_road_type` | 422 | 地理服务拒绝非公共机动车道路声明；HTTP schema 也可能先返回 validation_error |
| `service_area_unavailable` | 503 | 冻结地理文件不可读或结构/几何无效；启动失败 |
| `unsupported_upload_type` | 415 | 未使用要求的 multipart 上传格式 |
| `unsupported_image_type` | 415 | 可识别图片格式不是 JPEG/PNG |
| `invalid_image` | 422 | 图片为空、损坏、动画或无法解码 |
| `image_too_large` | 413 | 上传字节、整个请求或像素数量超过限制 |
| `image_not_found` | 404 | 巡检图片文件不存在 |
| `image_storage_unavailable` | 503 | 图片存储读写失败或路径不安全 |
| `image_already_exists` | 409 | 生成的目标图片已存在，拒绝覆盖 |
| `idempotency_conflict` | 409 | 相同请求 key 被用于不同内容 |
| `stale_record_version` | 409 | 巡检或任务记录版本已变化 |
| `invalid_state` | 409 | 该巡检不能再审核，或该任务已终止 |
| `invalid_detection_selection` | 422 | 选择的检测不属于此巡检 |
| `workflow_unavailable` | 503 | 巡检业务服务未就绪 |
| `task_query_unavailable` | 503 | 任务快照服务未就绪，不能返回空队列冒充成功 |

错误样例使用 `validation_error` / 422，details 中的 is_demo 标记属于固定样例附加 metadata，不要求真实响应添加。未来业务错误由对应服务明确抛出并记录，不能从固定样例推定已有业务逻辑。

## 调用方影响与验收

B 读取 Task 时必须识别 null 时长/null 期限以及 is_demo，不凭 label 猜规则；共同输入版本以 PlanningRevision 表示。C 展示 status、selected_detection_id、decision_trace 和演示来源，不自行推定严重度或分流阈值；前端模拟响应直接使用 contracts/examples 文件并保持标记。后台失败时不能用这些样例冒充真实成功响应。

`SystemCode/tests/test_contracts.py` 继续验证固定 DTO。第 6 步的 test_workflow、test_workflow_api、test_geography 和 test_images 覆盖持久化流程、真实 HTTP、地理边界、上传及回归。训练、真实检测、路线和完整项目端到端验证仍未完成。
