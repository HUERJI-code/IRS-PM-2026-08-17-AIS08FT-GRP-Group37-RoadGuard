# 第 7 步：A 向 B/C 的对接交付

日期：2026-10-12；负责人：A。此交付提供活动任务的一致查询、固定任务输入、可引用的项目知识及实际 HTTP 调用示例。巡检/任务仍使用明确的演示检测和规则；不代表 B 的规划、C 的页面/检索/助手或完整系统已经实现。

## 1. 交付入口和边界

| 使用者 | 交付物 | 入口 |
| --- | --- | --- |
| B | 无分页截断的任务快照服务与 HTTP 接口 | `roadguard.tasks.TaskQueryService`；`GET /api/v1/tasks/snapshot` |
| B/C | `a-task-query-v1` 数据模型 | [schemas/task_query.py](../SystemCode/backend/roadguard/schemas/task_query.py) |
| B | 10/15/20 个任务、空队列及边界输入 | [固定规划输入](../SystemCode/contracts/planning/README.md) |
| C | 带版本、来源和稳定引用 ID 的知识资料 | [知识包](../SystemCode/backend/knowledge/README.md) |
| C | 巡检/审核/任务请求、状态和错误 | [第 6 步指南](INSPECTION_REVIEW_TASK_WORKFLOW.md)、[API 契约](API_CONTRACT.md)、运行后的 `/docs` |
| B/C | 调用真实接口并导出响应的示例 | [handoff_demo.py](../SystemCode/examples/handoff_demo.py) |

这次冻结 A 的任务查询输出，不代替 B 定义完整 `PlanningInput`、Crew、RoutePlan、行程矩阵、班次或目标函数。C 的知识检索与生成仍由 C 实现；知识包不调用 GPT，也不建立向量索引。

## 2. B：读取同一版本的全部活动任务

```http
GET /api/v1/tasks/snapshot
GET /api/v1/tasks/snapshot?expected_revision=12
```

空数据库的实际响应结构：

```json
{
  "contract_version": "a-task-query-v1",
  "source": "persisted_workflow",
  "input_revision": 0,
  "tasks": [],
  "total": 0,
  "is_demo": true
}
```

| 字段/行为 | 约定 |
| --- | --- |
| tasks | 全部 active Task，使用原 `a-dto-v1` Task 精确字段；不含 TaskRecord 的 history/record_version 等额外字段 |
| total | 必须等于 tasks 长度；无默认 50 条或 100 条截断 |
| 顺序 | 按 created_at、task_id 升序，提供稳定节点排序基础；不是推荐访问顺序 |
| input_revision | 与任务在同一数据库读取事务中取得；不是任务数量，也不是某条记录版本 |
| expected_revision | 可选非负整数；不一致返回 409 stale_input_revision，不返回混合数据 |
| source | 在线查询是 persisted_workflow；固定 JSON 是 synthetic_fixture，不能冒充在线版本 |
| is_demo | 当前契约仅包含明确的演示任务；接真实模型后须另行协调契约 |
| 空队列 | 200、tasks=[]、total=0，仍带有效版本；数据库故障返回 503，不能伪装为空队列 |

查询无写入，不创建任务或增加版本。完成/取消任务从快照消失，但仍可通过任务详情/列表查询历史。无检测、待审核和驳回巡检从未形成活动任务。service_minutes=null 是未知时长，不得当作零；due_at=null 是无已知期限，不得编造延误。任务标签/优先级/时长取保存的 Task，不由 B 从标签重新推算。

页面分页仍使用 `GET /tasks?status=...&limit=...&offset=...`，其返回值为带历史的 TaskRecord。不要拼接可能属于不同版本的多页数据作为一次规划输入。TaskSnapshot 中每项可以直接交给原 Task DTO 解析，解决 strict DTO 不接受额外审计字段的问题。

### 后端内部共用连接

服务签名：

```python
TaskQueryService(database).snapshot(expected_revision=None, *, connection=None)
```

省略 connection 时，服务自行开启、关闭一次只读事务。B 将来需要把任务和工程队一起读取时，使用同一共享数据库连接：

```python
from roadguard.tasks import TaskQueryService

query = TaskQueryService(database)
with database.connect() as connection:
    snapshot = query.snapshot(connection=connection)
    # B 的 CrewService 将来在这里使用同一个 connection 读取队伍。
    # 不在这个上下文中调用会自行开启第二个连接的 crew 查询。

# 退出读取事务后再计算矩阵/Greedy/GA，避免长时间持有数据库事务。
# B 保存计算结果时，使用：
# with database.transaction(expected_revision=snapshot.input_revision) as connection:
#     在这里写入 B 的方案；保存方案本身不递增规划输入版本。
```

示例中的队伍读取和方案写入是 B 的待实现接入位置，不是现成的规划服务。调用者提供的 connection 必须来自同一个文件数据库，并已进入事务。TaskQueryService 不负责提交、回滚或关闭该连接；调用者负责生命周期。

快照是某个读取时刻的一致数据，不是对后续状态的锁定。任务/队伍可以在算法计算期间变化；保存方案时必须在写事务内再次核对 input_revision，冲突时丢弃过期计算结果或按 B 的策略重算，不能覆盖当前方案。不要只在计算前做一次版本检查。

HTTP 快照只包含任务。它不承诺通过另一个 HTTP 请求读取的队伍与任务同版本；B 内部组合输入应采用上述同连接方式。尚未实现自动任务变更事件、规划触发或旧方案标记；现有 mutation 响应的 planning_input_changed 供后续联调使用。

## 3. B：固定输入的使用

固定文件及可复现生成器见 [planning/README.md](../SystemCode/contracts/planning/README.md)。10/15/20 个任务使用同一基础序列的子集；不含行程矩阵、算法结果或训练图片。坐标经过冻结多边形校验，但都是合成点，未核验是否位于允许作业的道路上，不能直接当成实地任务或道路验证完成的实验集。

配置沿用四队和 NUS-ISS 建筑参考点，真实道路行程接入前仍需 B 核验基地车辆入口与任务道路资格。返基地、班次、期限和算法约束中的待确认值保持未知，不在样例中静默补全。

固定输入的 revision 只在该样例内有意义；不要传给在线 API 作为当前数据库版本。它们不会自动导入数据库，也不能作为查询失败时的备用成功响应。公平比较还需要 B 为 GA/Greedy 保持同一任务快照、队伍状态、节点顺序、行程矩阵和约束，另记录版本与随机种子。

## 4. C：知识检索与界面接入

知识包维护稳定文档/段落引用标识、来源和文件哈希、版本、责任方及一致性核对方式。核对是依据仓库现有事实进行的代码代理检查，不表示人类工程专家审批。明确区分项目已确认事实、演示假设和待定业务决定。

检索片段应保留其引用 ID、文档版本、分类和原始来源，回答附这些引用。`demo-rules-v1` 的说明不能自动解释采用其他冻结规则版本的任务；先核对保存的 rule_version 和决策/审计记录，版本资料不足时明确说明。

具体路线、队伍分配、行程时间与 GA/Greedy 指标必须来自 B 保存的对应 plan_id 数据，不从静态知识推测。当前没有路线结果时，不编造方案或“优化百分比”。工程队可用状态调整要经用户确认后调用 B 的服务；知识文本或模型回答不能直接写数据库。知识包中的问答验收案例用于检查未来实现，不是已运行 GPT/RAG 的实验结果。

前端对接注意：

- 显式选择 demo 案例；显示 is_demo、原始 confidence、decision_trace、rule_version，以及道路类型为调用者声明的事实。
- 无检测、待审核、接受、驳回分别显示；审核只对 pending_review 提供，确认/纠正必须选择检测。
- 一个逻辑动作重试时复用请求 key；真正的新动作才生成新 key。重新加载并解决冲突后提交修改，应生成新 request_id。
- 用 record_version 填 expected_version。409 stale_record_version 时刷新记录，不自动覆盖；409 idempotency_conflict 表示同一 key 被用于不同内容。
- 重试响应可能带来当前资源状态，不能假定它仍停留在首次操作时；replayed=true 不应再次显示“创建了新任务”。
- 当前 annotated_image_url=null，用保存的规范化图片与原图像素框绘制；图片宽高以响应为准。
- 任务变更后刷新队列；planning_input_changed=true 不等于已经取得新路线，不展示虚构的规划成功。

## 5. 运行真实 HTTP 对接示例

先按[后端安装说明](../SystemCode/backend/README.md)安装 requirements-ci.txt。以下 PowerShell 命令在仓库根执行；示例使用独立的开发数据库，保留生成的巡检和审计记录：

```powershell
$env:ROADGUARD_DB_PATH = 'SystemCode/backend/data/handoff-demo.sqlite3'
$env:ROADGUARD_UPLOAD_PATH = 'SystemCode/backend/data/handoff-demo-images'
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

另开终端，激活同一虚拟环境，在仓库根执行：

```powershell
python SystemCode/examples/handoff_demo.py --confirm-demo-writes
```

脚本通过真实 HTTP 请求生成一张合成 PNG，并验证自动接受、低置信度纠正、重复审核、无检测、驳回、任务完成/取消、一致快照和旧版本冲突。每次新增四条巡检，两条任务最终完成/取消；没有同时写入者时，活动任务集合恢复为运行前集合，input_revision 增加 4。不要针对正在多人操作的数据库执行此验收。

可加 `--base-url http://127.0.0.1:8001` 指定地址，或 `--output <已有目录中的新文件.json>` 导出实际请求结果，供 C 查看或制作明确标记的前端样例。输出文件不可覆盖已有文件，不应把本地运行记录提交进仓库。脚本会检查实际响应，失败立即报错，不返回伪造的成功数据；中途失败已经创建的演示记录仍保留，可从接口查询。

不传 --confirm-demo-writes 时脚本拒绝运行，避免读文档时无意向现有服务写入。导出结果不包含对应服务器的图片文件；其中的 image_url 只有在该服务器保存对应记录/图片时可访问。

## 6. 本步验收与下一步

```powershell
python -m pytest SystemCode/tests -q
```

测试覆盖完整查询（含超过 100 条）、原 Task 字段投影、未知值保留、终态过滤、输入版本冲突、并发一致性、外部连接生命周期、损坏数据失败、固定输入可复现、知识来源一致性，以及 HTTP 对接示例。没有执行真实模型训练、Google 行程获取、规划、GPT 调用或前端演示。

A 下一步是第 8 步的数据完整准备、分组划分、真实视觉模型训练与评估。B 可使用任务快照/固定输入开发调度；C 可使用现有 HTTP、知识包与引用验收案例开发界面和助手。组员接入后的跨模块联调仍是第 9 步。
