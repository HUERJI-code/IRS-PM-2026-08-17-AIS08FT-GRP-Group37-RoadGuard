# RoadGuard 共用后端基础

A maintains one FastAPI application, configuration, SQLite connection layer, errors and router registration. Implemented features include health checks, stateless demo previews, persisted image inspections/review/tasks and opt-in trusted local real vision. Real detections require review; business rules and tasks remain demo assumptions. Crews, routing, assistant and frontend remain pending. Public formats are in [API contract](../../Miscellaneous/API_CONTRACT.md); inspection responses now use a-workflow-v2, while a-task-query-v1 stays unchanged. See [real vision setup and API](../../Miscellaneous/REAL_VISION_API.md) for checkpoint provenance, optional dependencies, failure behavior and compatibility.

## 环境与启动

CI 使用 Python 3.11。`requirements.txt` 固定 FastAPI、Pydantic、Uvicorn，以及图片解码所需 Pillow、multipart 解析所需 python-multipart；`requirements-ci.txt` 引用它并添加 HTTPX 和 pytest。SQLite 使用标准库。已有环境也应重新安装依赖清单以取得新增包。

以下命令在仓库根目录执行，首次运行创建并激活本地虚拟环境：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r SystemCode/backend/requirements-ci.txt
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

本地地址：`http://127.0.0.1:8000/api/v1/health`；交互文档 `/docs`，OpenAPI `/openapi.json`。当前还声明巡检上传/查询/图片/审核和任务查询/修改。`roadguard.main.create_app(settings=None)` 创建可隔离应用；工厂不初始化数据库。lifespan 验证配置、演示规则与冻结地理资料后，执行数据库迁移。配置、目录权限或数据库结构错误使启动失败，不静默重建已有业务数据。此步面向本地开发，未新增身份认证或公开部署。

健康响应：

```json
{"status":"ok","database":"ok","api_version":"v1","input_revision":0}
```

此状态仅表示应用和 SQLite 基础可读，不表示模型、道路行程 API、GA 或助手已就绪。启动后数据库不可读、缺表或版本不兼容时返回 HTTP 503。

## 跑通第 5 步

在 `/docs` 中先调用 `GET /api/v1/demo/scenarios`，再向 `POST /api/v1/demo/assessments` 发送 `{"scenario_id":"high_confidence"}`。默认得到 P2、45 分钟的演示候选；`low_confidence` 得到 pending_review，`no_detection` 不产生候选。完整七个案例、阈值边界与八类演示映射见[模拟检测与规则指南](../../Miscellaneous/DEMO_DETECTION_AND_RULES.md)。这些接口不接收图片、不创建数据库记录，也不更新 input_revision。

## 第 7 步：任务和知识对接

`GET /api/v1/tasks/snapshot` 一次返回全部活动 Task 及同一事务的 input_revision，支持 expected_revision 查询参数；`/tasks` 保留页面分页/TaskRecord 历史用途。B 的内部入口是 `TaskQueryService(database).snapshot(expected_revision=None, *, connection=None)`，应用通过 `request.app.state.task_query_service` 提供实例。传入同数据库已有事务的连接可与 B 未来的队伍查询共用快照；服务不结束调用者事务。

完整契约、计算/保存时的版本检查、固定 10/15/20 任务、C 知识资料和实际 HTTP 消费示例见 [B/C 交接说明](../../Miscellaneous/BC_HANDOFF.md)。知识来源按仓库事实核对，不是工程专家审批；没有实现路线、检索/生成或前端。没有新增依赖或数据库迁移。

## 配置入口

The original demo upload/review/task behavior is documented in the [workflow guide](../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md). Uploads explicitly select demo mode with a named scenario, or real mode without a scenario. Real mode requires the optional locally configured detector; all nonempty real results wait for review. Accepted tasks remain persisted demo business objects. Road type is user-declared. The [Step 8 guide](../../Miscellaneous/REAL_VISION_API.md) describes this extension.

默认读取 `SystemCode/config/project.example.json` 与演示策略 `SystemCode/config/demo_rules.example.json`，默认数据库位置为 `SystemCode/backend/data/roadguard.sqlite3`。本地数据库不提交。支持以下环境变量：

| 变量 | 用途 |
| --- | --- |
| `ROADGUARD_CONFIG_PATH` | 指向本地 UTF-8 JSON 项目配置 |
| `ROADGUARD_DB_PATH` | 指向持久化 SQLite 文件 |
| `ROADGUARD_DEMO_RULES_PATH` | 覆盖演示规则配置路径；启动校验，修改后重启并更新规则版本 |
| `ROADGUARD_UPLOAD_PATH` | 图片保存目录，默认在数据库文件旁的 uploads 子目录；必须与数据库一起保存/备份 |
| `ROADGUARD_VISION_MANIFEST_PATH` | Optional trusted local model manifest; unset disables real inference. Relative paths resolve from the repository root. Model loading is lazy; restart after repairing a failed load. |

默认路径和相对覆盖值均相对仓库根目录解析，与启动时的工作目录无关；绝对路径仅作为用户本地覆盖值。路径留空、文件不可读、JSON 错误、重复键、非有限数字和基础对象结构错误会明确失败。`Settings` 不可变，其项目配置中的嵌套字典/列表也被冻结。基础校验只要求非空 `project_name` 及 `scenario`、`planning` 对象；未冻结的阈值、维修时长、班次和返基地策略不在此处猜测。示例配置的四队、地域和 `return_to_depot: null` 保持原义。未来模型/外部 API 凭据由所属模块定义环境变量，不写入示例文件或响应。

## 统一 SQLite 与规划输入版本

`roadguard.database.Database` 是各模块共用入口。每次操作获取独立连接并在退出时关闭；连接开启外键和 5000 毫秒 busy timeout。`connect()` 是只读事务，提供一致的查询快照；`transaction(expected_revision=None)` 使用 `BEGIN IMMEDIATE` 串行化写入，成功提交，异常回滚。不要在上下文内自行提交、回滚或关闭连接。

`initialize()` 是唯一迁移入口：基础 schema v1 原地迁移至 v2，保留 input_revision，新增 inspections、tasks、operation_keys 及索引；新数据库初始 revision=0。v2 重新启动校验已有结构；未知版本或缺失业务表拒绝启动，不清空/重建记录。B/C 后续业务表仍由负责人提供增量，A 在同一迁移入口整合。

供 A/B 共用的函数是 `read_revision(connection)`、`assert_revision(connection, expected_revision)` 和 `increment_revision(connection, expected_revision=None)`。输入变更与版本递增必须处于**同一个领域事务**，每次实际输入变更递增一次。不要使用独立计数器或事后第二次连接更新版本。例如，B 实现工程队状态服务时采用：

```python
from roadguard.database import increment_revision, read_revision

with database.connect() as connection:
    input_revision = read_revision(connection)
    # 从同一快照读取已实现的任务/工程队服务数据。

with database.transaction(expected_revision=input_revision) as connection:
    # 在这里调用所属领域的数据写入方法；尚未实现。
    new_revision = increment_revision(connection, expected_revision=input_revision)
```

示例仅说明事务边界，不是工程队实现。`expected_revision` 在写事务开始时校验；旧版本抛出 `StaleRevisionError`（HTTP 409），调用方尚未修改数据。版本递增不自行提交，领域写入失败时版本一并回滚。规划结果保存时也应在写事务内核对其输入版本；保存方案本身不改变规划输入，因此不应递增输入版本。如何触发重算、存储方案和报告过期状态由 B 的后续服务实现。

## 错误与模块接入

响应统一为 `{"code":"...","message":"...","details":null}`，details 可为 JSON 对象或列表。已实现错误：

| HTTP 状态 | code | 含义 |
| --- | --- | --- |
| 404 | `not_found` | 资源/路径不存在 |
| 405 | `method_not_allowed` | HTTP 方法不支持；保留 Allow 响应头 |
| 422 | `validation_error` | 请求验证失败，details 仅含 error_count |
| 409 | `stale_input_revision` | 旧输入版本；details 含 expected_revision/current_revision |
| 503 | `database_unavailable` | 健康检查无法读取有效基础数据库 |
| 500 | `internal_error` | 未处理错误，固定安全消息 |

其他 HTTPException 使用 `http_error` 及固定消息。错误响应不复制 URL、查询参数、验证输入、数据库路径、异常消息或 traceback。未来领域模块使用 `AppError(code, message, status_code, details)` 时，必须提供固定的可公开消息及安全的结构化 details，不能把异常或凭据传进去。未处理异常日志只记录异常类型。

B/C 提供各自 `APIRouter` 后由 A 在 `roadguard.api.create_api_router()` 统一注册到 `/api/v1`；数据库由 `request.app.state.database` 获取，配置由 `request.app.state.settings` 获取。领域服务负责业务语义和所属业务表，助手通过领域服务执行变更。当前不挂载空业务端点，也不在 API 服务失败时伪造模拟成功。

## 验证

仓库根目录执行与 CI 相同的入口：

```powershell
python -m pytest SystemCode/tests -q
```

基础测试覆盖配置、实际响应/OpenAPI、迁移、持久化、回滚和并发。vision/rules/demo API 验证固定案例、演示映射和预览不写库。第 6 步加入 geography/images/workflow/API 测试，覆盖图片/坐标、审核、任务状态、幂等、资源版本和历史规则快照。测试使用临时数据库和图片；它们不代表真实模型、道路网络核验、四队规划或完整系统已完成。
