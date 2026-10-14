# 固定任务快照：A → B/C

此目录提供 `a-task-query-v1` 的离线 `TaskSnapshot`，可使用 `roadguard.schemas.task_query.TaskSnapshot` 验证。`tasks` 内每项严格使用原公共 `Task` 字段，不含巡检/任务工作流的附加历史字段。它们是合成开发样例，不是运行中的数据库、实地任务、道路验证结果或已完成实验。

| 文件 | 用途 |
| --- | --- |
| `tasks_10.json` / `tasks_15.json` / `tasks_20.json` | 固定 10/15/20 个活动演示任务；10 是 15 的前缀，15 是 20 的前缀 |
| `tasks_empty.json` | 空活动队列的合法快照 |
| `tasks_unknown_service.json` | 独立的未知维修时长契约边界；`service_minutes=null`，不能当成零 |
| `manifest.json` | 来源文件 SHA-256、地理/基地/标签/规则版本、配置场景与样例限制 |
| `generate.py` | 从共享来源重现上述六个 JSON 文件；不读取或创建数据库 |

所有快照为 `source=synthetic_fixture`、`is_demo=true`，`input_revision=0` 只是固定样例标记，不代表在线数据库当前版本或任务数。ID、UTC 时间戳和点位顺序固定；任务均为 `active`。全部 `due_at=null`，不能凭这些样例计算期限延误。

标签按中央 [标签字典](../../model/label_schema.json) 的 class_id 循环排列，严重度、优先级、时长和规则版本从 [demo_rules.example.json](../../config/demo_rules.example.json) 读取，不维护第二套映射。当前 `planning-synthetic-v2` 对应 `demo-rules-v2`：P3/P2/P1＝60/120/240 分钟；同一个任务 ID 在不同 fixture_version 下内容可能不同，比较实验须同时记录样例版本与文件摘要。这是定稿的课程模拟假设，历史 v1 样例可从 Git 追溯。未知时长文件仅将一个衍生任务的时长显式置为 null，其他属性沿用共享规则；它是独立契约边界，不能称为当前完整规则映射的实际输出，也不加入 10/15/20 集合。

坐标从冻结 [JE/JW 多边形](../../../Miscellaneous/geography/jurong-boundary-mp2025.geojson) 内的固定网格合成，已检查多边形并集覆盖。**没有检查道路网络、道路类型或权限，点位可能不在道路上或落在被排除的道路上。** 因此可用于解析、地图加载和算法数据流开发；道路验证、行程矩阵、约束冻结及 B 的规划实现完成前，不能用作真实行程实验或性能结论。

四队 ID 和 NUS-ISS 起点的上下文来自 [项目配置](../../config/project.example.json)，manifest 记录这些值而不创建 Crew 模型。基地允许在任务区域外，实际车辆入口仍待核验。`shift_minutes` 与是否返基地仍未知；null 不代表无限班次或无需返基地。这里不生成矩阵、路线、GA/Greedy 结果或实验指标。

在仓库根目录使用后端统一环境运行：

```powershell
python SystemCode/contracts/planning/generate.py
python SystemCode/contracts/planning/generate.py --check
python -m pytest SystemCode/tests/test_planning_fixtures.py -q
```

生成器按自身源码位置解析仓库路径，从其他工作目录使用其绝对路径运行也得到相同内容。默认只写表中六个明确的 JSON 文件；`--check` 和测试在内存生成并比较，不修改 checkout。来源配置有变化时必须重生成并核对 manifest，不通过更新文档伪装成原样例。不得用这些文件自动初始化应用数据库，也不得在在线查询失败时作为成功回退。
