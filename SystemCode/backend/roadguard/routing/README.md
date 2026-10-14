# B 路线模块：四队调度、模拟行程矩阵、Greedy 与 GA

负责人：B。状态（2026-10-14）：已完成 B-1～B-3，即纯算法核心、自建 GA 和实验脚本。**尚未实现**：数据库表、CrewService、PlanningService、HTTP 接口（B-4），以及 Google 行程矩阵（B-5）。本模块目前不读写数据库，不注册路由，也不改变 `input_revision`。

## 1. 演示假设（集中配置）

[routing.example.json](../../../config/routing.example.json) 版本为 `b-routing-demo-v1`，`is_demo=true`。以下是 B 在 2026-10-14 选定的**演示假设，待 A 确认**，不是批准的运营规则：

| 项目 | 取值 | 说明 |
| --- | --- | --- |
| 收工返基地 | `return_to_depot: true` | 最后一个任务回到 NUS-ISS 的行程计入行程和完工时间。A 的 `project.example.json` 仍保持 `null`（未决定）。本模块不读取那个 null，也不把它解释为 false |
| 班次 | `shift_limit.mode: "unlimited"` | 明确选择不设上限；`limited` 时必须给出 `minutes`。这和“未知”不同 |
| 开始时刻 | 所有可用队伍在 `planning_start_at`（第 0 分钟）同时从 NUS-ISS 出发 | 符合“统一开始时刻重新规划”的首版语义；不跟踪在途车辆 |
| 等待 | 没有时间窗，行驶和维修连续进行 | `due_at` 只用来计算延误，不作为时间窗 |
| 模拟矩阵 | 球面距离 × 1.3 绕行系数 ÷ 30 km/h，保留 1 位小数 | `provider=simulated_haversine_v1`、`is_simulated=true`；不是道路网络或 Google 数据 |

## 2. 数据模型（`b-*-v1-draft`，尚未写入共享接口契约）

定义见 [models.py](models.py)。B-4 实现 HTTP 时再冻结到[接口契约](../../../../Miscellaneous/API_CONTRACT.md)。

- **PlanningInput**：`input_revision`、`planning_start_at`、`depot`、`crews`（全部配置的队伍，包括停用的）、`tasks`（a-task-query-v1 的 Task）、`settings`。任务只能是 active 状态，ID 唯一。
- **TravelMatrix**：`node_ids` 第 0 个是基地，之后按快照顺序排任务。`duration_minutes[i][j]` 表示 i→j 的行程，不假设对称，`null` 表示不可达。对角线必须为 0。
- **RoutePlan**：`plan_id`、`algorithm`（`ga`/`greedy`）、`crew_routes`、`unassigned_tasks`、`metrics`、`matrix_provider`、`matrix_is_simulated`、`settings`、`random_seed`、`algorithm_parameters`、`is_stale`、`is_demo=true`。
- **CrewRoute**：每支配置的队伍都输出一条，状态为 `assigned`、`idle` 或 `unavailable`。`stops` 按访问顺序排列，每站有到达和完工分钟数（相对开始时刻）。还包括 `travel_minutes`（含基地往返）、`return_travel_minutes`（不返基地时为 null）、`service_minutes`、`total_work_minutes`。`geometry=null`，前端只能画**标明示意的直线**。
- **未分配原因**：`unknown_service_minutes`、`unreachable_from_depot`、`unreachable_to_depot`、`no_available_crew`、`exceeds_shift_limit`、`no_feasible_route_position`。

`plan_routes()` 之后，`check_plan_covers_input()` 会断言每个输入任务恰好出现一次：要么在某条路线里，要么在未分配列表里。

## 3. 统一评估器与目标函数

[evaluation.py](evaluation.py) 中的 `RoutingProblem.evaluate()` 被 Greedy 和 GA 共用，保证约束和指标口径一致：

1. **预过滤**（两种算法相同）：未知工时、基地不可达、需要返回但回程不可达、没有可用队伍、单个任务就超过班次。这些任务直接列为未分配。
2. **解码**：每队按给定顺序依次检查。上一个点到该任务不可达，或者加入后超出班次（含回程），就跳过该任务并记录原因，不会悄悄丢弃。
3. **指标**：总行程（含首段和返程）、总维修时长、完工时间 makespan（最晚结束的可用队伍）、工作量标准差（可用队伍的行程加维修，闲置队伍记 0；停用队伍不计入）、优先级加权平均完工时间（P1/P2/P3 权重 3/2/1）。延误只对有 `due_at` 的任务计算；全部为 null 时，延误指标为 null，不会编造。
4. **目标**（`b-objective-v1`，演示权重，待 A 复核）：按字典序比较 `(未分配数, 加权成本)`。加权成本 = 1.0×makespan + 0.2×总行程 + 0.5×工作量标准差 + 0.5×优先级加权完工时间，单位都是分钟。第一位保证算法不能靠丢任务改善指标。**优先级加权完工时间不是延误**，只是在没有期限时对“紧急任务先完成”的替代度量。

## 4. Greedy 基线（[greedy.py](greedy.py)）

最早空闲的可用队伍先选。它在自己还能可行承担的剩余任务里取优先级最高的（P1 > P2 > P3）；优先级相同时取离当前位置行程最短的，再按快照顺序。某队已经没有可行任务时就停止。剩余任务交给评估器给出具体原因。结果是确定性的，没有随机种子。

## 5. 自建 GA（[ga.py](ga.py)）

- **染色体**：`order`（可调度任务的排列）加上 `owner[task]`（可用队伍编号）。每队按 `order` 中的先后访问自己的任务。owner 只从可用队伍中取，所以编码本身就保证停用队伍不会被分配，每个任务也只出现一次。
- **算子**：锦标赛选择（k=3）；`order` 用 OX 交叉，`owner` 用均匀交叉；变异随机选一种：交换、片段反转、换队、重定位。
- **精英保留** 2 个；**停止条件**是 300 代，或连续 80 代没有改进。种群 60，交叉率 0.9，变异率 0.3。
- **可复现**：所有随机数来自同一个 `random.Random(seed)`。实验默认使用种子 1～10。
- `seed_with_greedy=false`：默认不把 Greedy 解放进初始种群，避免对比时偏向 GA。开启时 GA 不会比 Greedy 差（有测试覆盖），但这不能当作算法优势。

## 6. 使用

```python
from roadguard.config import load_settings
from roadguard.routing import (build_planning_input, default_crews, depot_from_project,
                               load_routing_config, plan_routes, simulated_travel_matrix)

config = load_routing_config()
project = load_settings().project
planning_input = build_planning_input(snapshot, default_crews(project), depot_from_project(project),
                                      config.settings, "2026-10-15T01:00:00Z")
matrix = simulated_travel_matrix(planning_input, config.simulated_matrix)
greedy_plan, _ = plan_routes(planning_input, matrix, "greedy")
ga_plan, ga_result = plan_routes(planning_input, matrix, "ga", ga_parameters=config.ga, random_seed=1)
```

`snapshot` 可以是 `TaskQueryService.snapshot()` 的结果，也可以是固定样例 `TaskSnapshot`。B-4 将按[交接说明](../../../../Miscellaneous/BC_HANDOFF.md)的方式，在同一个只读事务里读任务和队伍，退出事务后再计算，保存方案前在写事务中再次核对版本。

实验脚本和结果见 [experiments/routing](../../../experiments/routing/README.md)。

## 7. 测试

```powershell
python -m pytest SystemCode/tests/test_routing_core.py SystemCode/tests/test_routing_ga.py SystemCode/tests/test_routing_experiments.py -q
```

覆盖：配置与校验、矩阵形状和节点顺序、空任务、单任务往返、不返基地、任务少于四队、停用一队、全部停用、未知工时、不可达（首段、回程、任务之间）、班次超限、Greedy 确定性与 P1 优先、10/15/20 任务不重不漏、延误计算、GA 固定种子可复现、精英单调、两种算法共享约束、算子合法性、实验脚本输出与拒绝覆盖。

## 8. 已知限制与后续

- 模拟矩阵只能说明算法在模拟行程上的表现，不能作为真实道路结论。B-5 接入 Google 前需要核验 NUS-ISS 的车辆入口，并单独获得 API 和费用授权。
- 固定任务点只经过多边形校验，没有核验是否在可作业道路上。
- 返基地、班次、目标权重和 GA 参数都是演示假设，需要 A 确认后才能作为正式口径。
- B-4 需要 A 统筹数据库迁移（v2→v3 新增 crews/route_plans 表）和路由注册；队伍状态变更要在同一事务中递增 `input_revision`。
