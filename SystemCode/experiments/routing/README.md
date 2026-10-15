# B 路线实验：四队 GA 与 Greedy 对比

负责人：B。设计依据见 [experiments/README.md](../README.md) 和[路线模块说明](../../backend/roadguard/routing/README.md)。

## 设计

| 项目 | 取值 |
| --- | --- |
| 场景 | 四队全部可用；共用 NUS-ISS 基地；返基地；每队每天班次上限 480 分钟（演示假设，待 A 确认） |
| 任务 | [固定样例](../../contracts/planning/README.md) `planning-synthetic-v2` 的 10/15/20 个任务（前缀关系），`due_at` 全部为 null |
| 行程 | `simulated_haversine_v1` 模拟矩阵；同一场景下 GA 和 Greedy 使用同一个矩阵（记录 SHA-256） |
| 开始时刻 | `2026-10-15T01:00:00Z`（新加坡 09:00） |
| Greedy | 每个场景运行 1 次（确定性） |
| GA | 种子 1～10，各运行 1 次；参数取自 `routing.example.json`，不用 Greedy 作初始解 |
| 比较 | 字典序 `(未分配 P1, 未分配 P2, 未分配 P3, 目标值)`，与算法优化的顺序一致；另报告各优先级未分配数、同时报告 makespan、总行程、工作量标准差、优先级加权完工时间、运行耗时 |

每次运行都写入 `raw_runs.csv`，包括 GA 不如 Greedy 的种子。`ga_convergence.csv` 记录每代的最优值，`summary.json` 是统计汇总，`run_metadata.json` 记录配置全文和哈希、样例哈希、代码 commit、Python 和平台信息。

## 复现

在仓库根目录执行。输出目录已存在时会拒绝覆盖：

```powershell
python SystemCode/experiments/routing/run_experiments.py --output-dir SystemCode/experiments/routing/results/<新目录>
# 可选，需要本地安装 matplotlib（不在后端 CI 依赖中）
python SystemCode/experiments/routing/plot_results.py SystemCode/experiments/routing/results/<新目录>
```

除 `algorithm_runtime_ms` 和 `matrix_preparation_ms` 外，同一配置和种子会得到相同的指标（有测试覆盖）。

## 已保存的结果

2026-10-15 运行了四组实验：模拟矩阵（代码 `7651947`）和 Google 矩阵（代码 `06cb76b`），各有 480 分钟班次和不限班次两组。原始数据、矩阵、图和结论见 [results/README.md](results/README.md)。

`--matrix-provider google_routes` 会调用收费的 Google API（默认任务数下只请求一次 21×21 矩阵），`--unlimited-shift` 取消班次上限做敏感性对比，两者都会记录在 `run_metadata.json` 中。运行前工作区应保持干净（包括未提交的旧结果目录），否则元数据会记为 `working_tree_dirty=true`。

`diagnose_tight_capacity.py` 复现并诊断 Google 矩阵、480 分钟班次、15 个任务场景中纯 GA 漏排任务的原因，只读取已保存的矩阵并打印结果，见 [results/README.md](results/README.md) 6.6 节。

## GA 评估（消融与离已知最好解的差距）

`evaluate_ga.py` 回答“GA 本身表现如何”，不只看“是否优于 Greedy”。它直接读取 B6 保存的矩阵（核对哈希和节点顺序，不请求 Google），在 2 种矩阵 × 2 种班次 × 10/15/20 个任务共 12 个场景下比较：

- `greedy`：基线；
- `ga_pure`：实验用 GA，种子 1～10；
- `ga_seeded`：在线用 GA（初始种群含 Greedy 解），种子 1～10；
- `long_run`：大预算（种群 150、最多 1000 代、耐心 300 代），种子 101～120，纯 GA 和 Greedy 初始化交替。只用来寻找已知最好解（BKS）。

BKS 是所有运行中最好的方案，**不保证是真正的最优**。离 BKS 的差距只在排进的任务和 BKS 一样多时才计算；排进更少的单独记为 `fewer_tasks_than_bks`。

```powershell
python SystemCode/experiments/routing/evaluate_ga.py --output-dir SystemCode/experiments/routing/results/ga-evaluation-v1
```

单机约 6～7 分钟。输出 `raw_runs.csv`、`summary.json`、`best_known.json`（含 BKS 路线）和 `run_metadata.json`。正式结果和分析见 [results/README.md](results/README.md) 第 7 节。

## 限制

- 行程为模拟值，不能据此宣称真实道路上的时间节省或费用节省。
- 运行耗时是单机墙钟时间，与外部 API 等待分开（模拟矩阵没有 API 等待）。
- 没有任务期限，所以不报告延误；优先级加权完工时间不是延误。
- 目标权重和 GA 参数是演示提案，没有在独立数据上调参。
