# B 路线实验：四队 GA 与 Greedy 对比

负责人：B。设计依据见 [experiments/README.md](../README.md) 和[路线模块说明](../../backend/roadguard/routing/README.md)。

## 设计

| 项目 | 取值 |
| --- | --- |
| 场景 | 四队全部可用；共用 NUS-ISS 基地；返基地；不设班次上限（演示假设，待 A 确认） |
| 任务 | [固定样例](../../contracts/planning/README.md) `planning-synthetic-v2` 的 10/15/20 个任务（前缀关系），`due_at` 全部为 null |
| 行程 | `simulated_haversine_v1` 模拟矩阵；同一场景下 GA 和 Greedy 使用同一个矩阵（记录 SHA-256） |
| 开始时刻 | `2026-10-15T01:00:00Z`（新加坡 09:00） |
| Greedy | 每个场景运行 1 次（确定性） |
| GA | 种子 1～10，各运行 1 次；参数取自 `routing.example.json`，不用 Greedy 作初始解 |
| 比较 | 字典序 `(未分配数, 目标值)`；同时报告 makespan、总行程、工作量标准差、优先级加权完工时间、运行耗时 |

每次运行都写入 `raw_runs.csv`，包括 GA 不如 Greedy 的种子。`ga_convergence.csv` 记录每代的最优值，`summary.json` 是统计汇总，`run_metadata.json` 记录配置全文和哈希、样例哈希、代码 commit、Python 和平台信息。

## 复现

在仓库根目录执行。输出目录已存在时会拒绝覆盖：

```powershell
python SystemCode/experiments/routing/run_experiments.py --output-dir SystemCode/experiments/routing/results/<新目录>
# 可选，需要本地安装 matplotlib（不在后端 CI 依赖中）
python SystemCode/experiments/routing/plot_results.py SystemCode/experiments/routing/results/<新目录>
```

除 `algorithm_runtime_ms` 和 `matrix_preparation_ms` 外，同一配置和种子会得到相同的指标（有测试覆盖）。

## 限制

- 行程为模拟值，不能据此宣称真实道路上的时间节省或费用节省。
- 运行耗时是单机墙钟时间，与外部 API 等待分开（模拟矩阵没有 API 等待）。
- 没有任务期限，所以不报告延误；优先级加权完工时间不是延误。
- 目标权重和 GA 参数是演示提案，没有在独立数据上调参。
