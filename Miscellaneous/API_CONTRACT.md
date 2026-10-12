# A 第一版公共 DTO 契约

版本：`a-dto-v1`；日期：2026-10-12；维护人：A。此文件是已落实的 A 公共 DTO 契约唯一维护位置。分工表第 6、7 节保留成员职责与未来接口设计，涉及已落实的字段定义应链接本文件；B/C 后续对象由对应负责人提出，不从本文件推定其已冻结。可执行来源为 [schemas](../SystemCode/backend/roadguard/schemas/)，固定样例为 [contracts](../SystemCode/contracts/README.md)。变更必须同时更新 DTO、样例、必要测试与调用方影响说明。

本次冻结数据表示和最低一致性验证，不等于完成 M0：置信度阈值、标签与业务规则映射、多检测选取策略、维修时长、期限和调度参数仍待确认。严禁把样例升级为批准规则。公共导入为 `from roadguard.schemas import Detection, Inspection, Task, ErrorResponse, HealthResponse, PlanningRevision`；另提供结构化 `DecisionTrace`。

## 通用表示

- JSON 字段使用 `snake_case`；ID 与版本用非空字符串，前后空白被去除，纯空白无效。未知字段拒绝，防止调用方静默拼错字段。
- 数值只接受 JSON 数字，不接受字符串或布尔值；整数（类编号、图像尺寸、输入版本）拒绝小数。浮点数必须有限。`is_demo` 只接受布尔值并且显式提供。
- 坐标为 WGS84 十进制度：`latitude` [-90,90]，`longitude` [-180,180]。DTO 验证不代表 JE/JW 多边形或允许道路校验通过；未来任务业务服务另行执行地域/道路约束。
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

Inspection 内 detection_id 必须唯一；非空 selected_detection_id 必须指向本巡检的检测。`no_detection` 必须没有检测、选中对象和任务；其余状态必须有检测。`pending_review` / `rejected` 无 task_id，选中对象允许为空；`accepted` 必须有选中对象和 task_id。含演示检测或演示 trace 的巡检必须标为 is_demo=true；各步骤可保留不同来源（例如真实检测配演示规则），不把真实检测误标为模型演示。DTO 校验只检查快照内关联，跨对象 inspection_id/task_id、重复确认、任务状态转换和持久化约束留给未来服务；样例测试另外验证固定快照的跨对象一致性。

## 路由实现状态与错误

当前实际业务路由只有 `GET /api/v1/health`，200 返回 HealthResponse。巡检上传/查询/审核、任务查询/修改、队伍、规划与助手路径仍是分工表第 7 节的未来接口；本次没有为这些路径注册返回样例的伪业务处理器，也没有冻结其请求体或分页格式。OpenAPI 仅展示已注册路由，DTO 文件存在不表示其 API 已存在。

统一错误的可执行来源为 [errors.py](../SystemCode/backend/roadguard/errors.py) 及 [health.py](../SystemCode/backend/roadguard/api/health.py)；使用 `code` 判断，不匹配 message 文本。当前错误码如下，变更须与实现同步：

| code | HTTP 状态 | 当前含义 |
| --- | --- | --- |
| `validation_error` | 422 | FastAPI 请求校验失败，details 仅 error_count，不回显原始输入 |
| `not_found` | 404 | 未注册路径或明确的资源不存在 HTTP 错误；不意味着任务查询 API 已实现 |
| `method_not_allowed` | 405 | 已有路径不支持该方法，保留 Allow header |
| `stale_input_revision` | 409 | 共享数据库修订服务拒绝旧预期版本；无规划 HTTP handler |
| `database_unavailable` | 503 | health 的数据库检查失败 |
| `internal_error` | 500 | 未处理异常的安全公共说明，无原始异常文字 |
| `http_error` | 对应 HTTP 状态 | 其他 HTTPException 的通用安全说明 |

错误样例使用 `validation_error` / 422，details 中的 is_demo 标记属于固定样例附加 metadata，不要求真实响应添加。未来业务错误由对应服务明确抛出并记录，不能从固定样例推定已有业务逻辑。

## 调用方影响与验收

B 读取 Task 时必须识别 null 时长/null 期限以及 is_demo，不凭 label 猜规则；共同输入版本以 PlanningRevision 表示。C 展示 status、selected_detection_id、decision_trace 和演示来源，不自行推定严重度或分流阈值；前端模拟响应直接使用 contracts/examples 文件并保持标记。后台失败时不能用这些样例冒充真实成功响应。

`SystemCode/tests/test_contracts.py` 验证全部固定样例、跨对象链接、标签对照、框/数值/坐标边界、状态约束、UTC 与非法输入。本次仅提供 DTO 层验证证据，不声称训练、检测、规则、任务、地理校验或端到端流程已完成。
