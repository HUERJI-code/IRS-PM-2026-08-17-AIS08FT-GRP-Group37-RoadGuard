# 未定选项与后续证据

document_id：`rg-kb-pending`；document_version：`2`；owner：`A`。

<a id="pending-business"></a>
## 业务与场景待确认

classification：`pending_decision`。citation_id：`rg-kb-pending#pending-business`。

待 A/B 确认班次长度、是否返基地、工程队能力假设、正式维修分钟数、任务期限/延误定义及目标权重；待 A 校准真实模型阈值、正式标签映射和多检测形成任务的策略。demo-rules-v1 只让流程可演示，不解决这些正式业务问题。NUS-ISS 建筑参考坐标仍需 B 核验车辆出入口，任务道路资格与真实矩阵来源另需证据。

due_at=null 时没有已定义的任务期限；return_to_depot=null 时没有已定义的返程策略。未知时长不是零，无可用方案不是空的有效方案，不可达行程不是零分钟。

来源：[src-project-config](../../config/project.example.json)、[src-demo-rules](../../config/demo_rules.example.json)、[context-agents](../../../AGENTS.md)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)。

<a id="pending-evaluation"></a>
## 算法、模型与联调证据

classification：`pending_decision`。citation_id：`rg-kb-pending#pending-evaluation`。

主要比较场景为四队和 10/15/20 个任务；GA 与 Greedy 使用相同输入、行程矩阵和约束。编码、参数、停止条件、目标函数权重及多个随机种子仍需 B 交付，不预先宣称 GA 更优。报告算法运行时间、外部 API 等待、行程/维修时长时必须分开，不以更多队伍推断算法更快。

完整数据内容验证、划分与真实模型训练/held-out 指标须引用第 8 步对应运行的实际记录。模型数值有效不等于达到业务准确率要求，实验模型不能被描述为已校准的自动接受系统。B 的持久化路线事实、C 的检索/引用/确认流程及端到端联调仍需实际成果。本知识包的完整性测试和验收题不能当作这些能力已经完成的证据。

来源：[src-project-config](../../config/project.example.json)、[context-agents](../../../AGENTS.md)、[context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)。
