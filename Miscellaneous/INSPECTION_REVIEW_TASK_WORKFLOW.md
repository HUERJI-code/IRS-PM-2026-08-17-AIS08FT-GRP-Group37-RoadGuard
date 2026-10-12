# 第 6 步：巡检、审核与任务

负责人：A；日期：2026-10-12；增量契约：`a-workflow-v1`。本步实现图片上传、范围校验、巡检与审核持久化、任务管理及同事务输入版本更新。所有检测仍由调用者明确选择的模拟案例生成，规则仍使用 `demo-rules-v1` 等明确标记的演示策略；不从图片像素识别损坏，不调用 Google、YOLO 或 GPT，不生成路线。

## 1. 巡检与任务的区别

有效提交保存一条 `InspectionRecord`。它保留图片地址、坐标、原始检测框/标签/置信度、模型来源、规则决策过程、审核历史和记录版本。只有接受的巡检才关联一条 `TaskRecord`；数据库对 `task.inspection_id` 加唯一约束，防止重复建任务。

| 检测结果 | 巡检状态 | 任务与规划输入版本 |
| --- | --- | --- |
| 无检测 | `no_detection` | 保存巡检；没有任务；不递增 input_revision |
| 任一检测低于演示阈值 | `pending_review` | 保存所有检测；等待审核；不递增 |
| 所有检测达到演示阈值 | `accepted` | 按演示规则选择一个候选并创建任务；递增一次 |
| 待审核巡检确认或纠正 | `accepted` | 根据明确选择的检测及审核结果创建一个任务；递增一次 |
| 待审核巡检驳回 | `rejected` | 保留记录和审核说明；没有任务；不递增 |

一条巡检最多对应一个任务的行为沿用第 5 步的演示策略，不表示正式多检测业务决策已经验证。无检测记录不能通过审核接口凭空补出检测；需要重新提交。已接受/驳回的巡检不重新审核；接受后如需修正，走任务修改接口。任务完成或取消保留历史，不物理删除，也不允许重新激活。

人工确认不会把原始置信度改成 1.0；纠正也不会覆盖模型原始标签。`review_history` 单独保存选中检测、原标签、纠正标签、操作、说明、时间和规则版本。审核与后续任务标签修正使用该巡检保存的完整规则配置快照，避免服务重启后新配置悄悄改写旧巡检规则。

## 2. 图片、位置和道路声明

- 上传仅接收能够完整解码的单张 JPEG/PNG：原始文件最多 8 MiB，最多 2,000 万像素；拒绝损坏文件、动画、其他格式和超限文件。HTTP 层在解析 multipart 前限制总请求为 8 MiB + 64 KiB，metadata 最多 16 KiB，不依赖 Content-Length 声明。
- 图片按 EXIF 方向规范化为无原始 metadata 的 RGB PNG。模拟框按保存图片的尺寸缩放；它们是合成框，不是对所上传照片的识别结果。暂不生成单独标注图，`annotated_image_url=null`；C 可根据返回框在页面绘制。
- 文件名由服务端生成，不采用用户文件名。通过 `/inspections/{id}/image` 访问，必须有对应数据库记录；不会公开整个上传目录。
- 经纬度必须是有限 JSON 数字，按 WGS84 范围校验，再按冻结的 JE/JW 多边形并集校验，包含边界。不会用外接矩形代替多边形。NUS-ISS 只作为基地拥有区域外例外，用它提交维修任务仍被拒绝。
- 必须显式提交 `road_type: "public_motor_road"`。该声明应符合[道路排除规则](JURONG_SCOPE_AND_DEPOT.md)，服务拒绝其他类别，记录 `road_type_source: "user_declared"`。目前没有道路网络/通行权限核验，**声明不是道路资格的自动验证**；调用者须核对位置，正式实验点位仍由 A/B 另行核验。
- 坐标与照片是分开提交的数据；不据此证明照片拍摄于 Jurong。所有巡检和任务保持 `is_demo=true`，上传必须写明 `mode:"demo"` 和案例 ID，不提供真实模型失败后自动回退的行为。

无效上传、范围外位置或未知案例不创建有效巡检或任务；存储失败不能返回成功。业务数据库与图片应一起备份。数据库事务失败会清理该请求新建的图片；进程在写文件与提交数据库之间异常退出可能留下孤立文件，它们不能通过图片 API 访问。当前不自动删除这些文件，也不提供跨文件系统和 SQLite 的原子事务保证。

## 3. HTTP 接口

统一前缀 `/api/v1`，交互说明为后端 `/docs`，错误使用公共 `ErrorResponse`。原 `/demo` 预览仍不写数据库。

| 方法与路径 | 输入 | 正常输出 |
| --- | --- | --- |
| `POST /inspections` | multipart 的 `image` 文件、`metadata` JSON 文本；请求头 `Idempotency-Key` | 新建 201；相同请求重试 200；`InspectionMutation` |
| `GET /inspections` | 可选 status、limit、offset | `InspectionList` |
| `GET /inspections/{id}` | 巡检 ID | `InspectionRecord` |
| `GET /inspections/{id}/image` | 巡检 ID | 规范化后的 image/png |
| `POST /inspections/{id}/review` | `ReviewRequest` | `InspectionMutation` |
| `GET /tasks` | status 默认 active，可取 all/completed/cancelled；limit、offset | `TaskList`，含同一读取快照的 input_revision |
| `GET /tasks/{id}` | 任务 ID | `TaskRecord`，包含历史 |
| `PATCH /tasks/{id}` | `TaskPatch` | `TaskMutation` |

列表默认 limit=50、offset=0；limit 为 1～100，offset 非负；支持状态筛选，包含 total。巡检默认所有状态。分页是单次请求的一致快照，多页期间可能有新业务变更；B 不应把不同 input_revision 的任务页混成一轮规划。

### 上传

`UploadMetadata` 必须且仅包含：

```json
{
  "mode": "demo",
  "scenario_id": "low_confidence",
  "latitude": 1.34,
  "longitude": 103.72,
  "road_type": "public_motor_road"
}
```

上述坐标仅说明接口格式，不是已核验道路的实验点。使用自己核对过的范围内公共机动车道路位置。案例从 `GET /api/v1/demo/scenarios` 获取。

将 JSON 保存为本地 `upload-metadata.json`，准备一张合法图片，在 PowerShell 执行：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/inspections" -H "Idempotency-Key: inspection-demo-001" -F "image=@sample.jpg" -F "metadata=<upload-metadata.json"
```

同一逻辑提交重试时保留 Idempotency-Key；真正新增巡检使用新 key。key 只接受 1～64 个英文字母、数字、下划线或连字符。相同 key 携带不同原始文件内容或 metadata 返回 409，不会覆盖原记录。不能通过改文件名骗过或改变请求指纹；原始上传字节和规范化后的 metadata 才参与指纹。

### 审核

从巡检响应取得 `inspection_id`、`record_version` 和 `detection_id`：

```json
{
  "request_id": "review-demo-001",
  "expected_version": 1,
  "action": "correct",
  "detection_id": "demo-low_confidence-01",
  "damage_label": "pothole_deep",
  "note": "Corrected the selected synthetic damage label."
}
```

- `confirm` 必须指定本巡检中的 detection_id，不能传 damage_label。
- `correct` 必须同时提供 detection_id 和中央标签字典中的 damage_label。
- `dismiss` 不得提供选择或纠正字段；三种操作均可携带最多 500 字符的 note。
- 仅 `pending_review` 可以发生新的审核。多框情况下，审核者明确选择代表检测，其他原始框继续保留；这是对整条巡检的明确审核决定。
- 当前不实现登录/身份认证，因此 audit 的 `actor_source` 表明它是未经身份核验的调用者操作，不能把记录描述为认证人员签名。

### 修改任务

```json
{"request_id":"complete-demo-001","expected_version":1,"status":"completed"}
```

允许字段：status 为 completed/cancelled；damage_label 为中央标签；或 latitude、longitude、road_type 三个字段一起更新。标签修正由服务端重算优先级、严重度、工时和维修建议，并记录前后值。位置修正重新做范围校验，保留巡检的原始提交位置。拒绝空修改、显式 null、不完整位置、任意填写 priority/service_minutes/due_at 和重开任务。

任务期限保持 null，不编造延期；未知维修时长仍为 null，不用零替代。终态记录仍可按 ID 或状态筛选查询。

## 4. 版本、幂等与返回值

`record_version` 是某条巡检/任务的乐观并发版本，审核/修改必须带 expected_version；过期请求返回 409。`input_revision` 是共同规划输入版本；一次实际任务创建、修正、完成或取消只在同一事务中递增一次。重复请求、未改任何业务值的请求、待审核/无检测保存和驳回不增加规划版本。

审核/任务修改用 request_id 防重，范围分别是该巡检的审核和该任务的修改。完全相同的重试优先识别，旧 expected_version 不阻止安全重放；同一 request_id 改动内容返回 409。重放返回**当前**资源和当前输入版本，不返回可能已经过时的历史响应。

- `InspectionMutation`：inspection、可空 task、input_revision、planning_input_changed、replayed。
- `TaskMutation`：task、input_revision、planning_input_changed、replayed。
- planning_input_changed 仅表示此次请求真正改变规划输入；它不是“路线已计算完成”。第 6 步不调用尚未实现的 B 规划服务，也不返回虚构方案 ID。
- InspectionRecord/TaskRecord 在基础 DTO 之上新增时间、record_version、来源和历史等字段。原基础 DTO 设置 extra=forbid，不能直接解析包含这些额外字段的新 HTTP 记录；C 应使用新记录契约，B 使用明确的 Task 字段投影或新记录类型。旧 `a-dto-v1` 固定样例保持原义。

可执行 schema 位于 [workflow.py](../SystemCode/backend/roadguard/schemas/workflow.py)，公共错误入口见[API 契约](API_CONTRACT.md)。前端根据 code/status 决定行为，不匹配自然语言错误说明。

## 5. 数据库与验证

启动把已有基础数据库 schema v1 原地迁移为 v2，保留 input_revision；新增 inspections、tasks、operation_keys 和索引。迁移和业务写入都使用共享 SQLite 事务；不删除旧数据、不另建业务数据库。未知或损坏的版本结构拒绝启动。

默认图片目录在数据库旁的 uploads 子目录；`ROADGUARD_UPLOAD_PATH` 可独立覆盖，路径以仓库根目录解析。设置 `ROADGUARD_DB_PATH` 后，默认图片目录随数据库配置位置变化，适合隔离本地测试；配置变更不会自动搬移已有文件。重启复用数据库和图片目录即可读取原记录。

验证入口仍是 `python -m pytest SystemCode/tests -q`，覆盖七个案例、图片与范围边界、审核原始证据保留、任务状态、幂等与并发、事务回滚、规则快照、迁移和重启。测试图片在临时目录生成，不提交上传图片或真实巡检数据库。

第 7 步已交付[完整 B/C 对接资料](BC_HANDOFF.md)，包括一致任务快照、固定输入与知识来源；第 8 步准备训练并接真实模型。四队调度、助手、网页与完整系统联调仍按原分工推进。
