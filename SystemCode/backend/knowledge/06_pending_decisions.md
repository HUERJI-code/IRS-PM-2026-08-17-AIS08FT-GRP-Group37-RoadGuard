# 未定选项与后续证据

document_id：`rg-kb-pending`；document_version：`5`；owner：`A`。

<a id="pending-business"></a>
## 业务与场景待确认

classification：`pending_decision`。citation_id：`rg-kb-pending#pending-business`。

2026-10-14 已定稿课程模拟规则 demo-rules-v2：保持八类的严重度/优先级映射，P3/P2/P1 的预计维修时长分别为 60/120/240 分钟。单主框 ≥ 0.60 自动建一个任务，低于阈值待审核。上述工时不是任务期限或测量值；正式工程规则与真实场景校准仍缺证据。待 A/B 确认班次长度、是否返基地、工程队能力假设、任务期限/延误定义及目标权重。NUS-ISS 建筑参考坐标仍需 B 核验车辆出入口，任务道路资格与真实矩阵来源另需证据。

due_at=null 时没有已定义的任务期限；return_to_depot=null 时没有已定义的返程策略。未知时长不是零，无可用方案不是空的有效方案，不可达行程不是零分钟。

来源：[src-project-config](../../config/project.example.json)、[src-demo-rules](../../config/demo_rules.example.json)、[context-agents](../../../AGENTS.md)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)。

<a id="pending-evaluation"></a>
## 算法、模型与联调证据

classification：`pending_decision`。citation_id：`rg-kb-pending#pending-evaluation`。

主要比较场景为四队和 10/15/20 个任务；GA 与 Greedy 使用相同输入、行程矩阵和约束。B 已交付编码、参数、停止条件、目标函数和多种子实验；具体结论必须读取对应实验原始记录，本包不复制或扩展实验数值，不预先宣称 GA 更优。报告算法运行时间、外部 API 等待、行程/维修时长时必须分开，不以更多队伍推断算法更快。

完整数据内容验证、划分与真实模型训练/held-out 指标须引用第 8 步对应运行的实际记录。模型数值有效不等于达到业务准确率要求，实验模型不能被描述为已校准的自动接受系统。B 已有持久化方案，队友已记录主流程联调；C 第十步提供静态检索，GPT 问答和调整确认仍待实现和分别验收。本知识包的完整性测试和验收题不能当作这些能力已经完成的证据。

来源：[src-project-config](../../config/project.example.json)、[context-agents](../../../AGENTS.md)、[context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)。

补充来源：[src-routing-guide](../roadguard/routing/README.md)。
