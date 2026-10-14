# B 路线实验：四队 GA 与 Greedy

本目录提供 B-3 的模拟实验入口。算法、约束和待确认的演示假设见[路线模块说明](../../backend/roadguard/routing/README.md)，参数集中在 [routing.example.json](../../config/routing.example.json)。当前提交包含实验与绘图脚本，不包含完整实验结果；不能将脚本已实现视为 GA 已优于 Greedy。

## 输入与比较口径

- 默认四支工程队，共用 NUS-ISS 模拟基地。
- 使用[固定任务快照](../../contracts/planning/README.md)中的 10、15、20 个合成任务；任务点仅经过 Jurong 多边形检查，未核验道路。
- 每个规模的 Greedy 和 GA 使用相同任务、工时、队伍、基地、开始时刻、约束和行程矩阵。
- Greedy 是确定性的，每个规模执行一次；GA 默认使用配置中的种子 1～10，各执行一次。
- 行程来自 `simulated_haversine_v1`，不是 Google 或真实道路网络数据。返基地、无限班次与目标函数权重均为待确认的演示假设。
- 固定任务的 `due_at` 为 null，因此不报告实际延误；优先级加权完工时间不等于延误。

## 运行

先按[后端说明](../../backend/README.md)准备 Python 环境和依赖。以下命令在仓库根目录执行；输出放入本地忽略的 `Dataset/`，不要上传数据与运行缓存。

完整默认比较（3 个规模，共 3 次 Greedy 和 30 次 GA）：

```powershell
python SystemCode/experiments/routing/run_experiments.py --output-dir Dataset/routing-experiments/simulated-v1
```

只运行一个规模和两个种子：

```powershell
python SystemCode/experiments/routing/run_experiments.py --output-dir Dataset/routing-experiments/check-10 --task-counts 10 --seeds 1 2
```

每次使用新的输出目录；脚本拒绝覆盖已存在的目录。`--seeds` 只改变随机种子，GA 种群和代数仍读取配置。

## 输出与复核

| 文件 | 内容 |
| --- | --- |
| `raw_runs.csv` | 每次运行的分配/未分配数、行程、维修、完工时间、工作量标准差、优先级加权完工时间、目标值及算法耗时；另记矩阵准备耗时 |
| `ga_convergence.csv` | 每个规模和种子的逐代最优未分配数及目标值 |
| `summary.json` | Greedy 指标、GA 各种子的统计值、优于/等于/差于 Greedy 的种子数量，以及任务和矩阵摘要 |
| `run_metadata.json` | 实际配置、种子、Git 提交及工作区状态、Python/平台信息、生成时刻和实验限制 |

比较首先考虑未分配任务数，再比较加权目标值；不能只挑 GA 获胜的种子。每个成功生成的方案都经过任务覆盖检查。运行脚本遇到异常会失败，应保留错误记录并排查，不能把失败写成成功结果。

可选绘图需要本地安装 `matplotlib`（不属于后端 CI 必需依赖），从上述 CSV 生成 `ga_vs_greedy.png` 和 `ga_convergence.png`：

```powershell
python SystemCode/experiments/routing/plot_results.py Dataset/routing-experiments/simulated-v1
```

## 验证

```powershell
python -m pytest SystemCode/tests/test_routing_core.py SystemCode/tests/test_routing_ga.py SystemCode/tests/test_routing_experiments.py -q
python .github/scripts/check_repository.py
```

自动测试验证算法约束、固定种子和实验记录行为；小规模测试不代替完整多种子实验，也不证明真实道路调度效果。当前模块尚未接入数据库、HTTP 规划接口或 Google 行程矩阵。
