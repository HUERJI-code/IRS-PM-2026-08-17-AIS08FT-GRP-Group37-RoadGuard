# 助手回答与修改的证据边界

document_id：`rg-kb-assistant`；document_version：`1`；owner：`A`。

<a id="assistant-plan-facts"></a>
## 动态路线事实

classification：`confirmed_project_fact`。citation_id：`rg-kb-assistant#assistant-plan-facts`。

以下是已记录的项目对接要求，待 B/C 实现，不是本包提供的助手/规划功能。路线回答必须绑定 B 保存的 plan_id 与其 input_revision，使用对应 crew_routes、停靠顺序、未分配项、metrics、matrix_provider 和 stale 信息；比较须取明确的两个保存方案。A 的静态知识只能解释范围/标签/规则，不能提供当前队伍分配、到达时间或总行程分钟数。

无持久化方案或相关事实时返回 insufficient_data，列出缺少的方案和字段。不要从图片、任务排序、模型回答或样例造出路线；不能把示意直线当道路几何，也不能把模拟矩阵描述成 Google 实测。过期方案和失败必须明确显示，不替换成新的虚构结果。

来源：[context-agents](../../../AGENTS.md)、[context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md)、[src-project-config](../../config/project.example.json)。

<a id="assistant-confirmation"></a>
## 队伍调整必须确认

classification：`confirmed_project_fact`。citation_id：`rg-kb-assistant#assistant-confirmation`。

首批助手修改范围仅为队伍可用状态：先结构化预览，再由用户明确确认，经 B 的 CrewService/规划业务服务校验旧输入版本、执行与重算；取消、过期和重复确认要有明确结果。助手和 C 不直接写任务/队伍/方案业务表，也不另建调度算法。新任务走 A 的巡检/审核流程，不能让自然语言自由填写优先级、期限或维修时长。上述是未来对接政策，当前不能声称停队、重算或确认接口已经执行成功。

来源：[context-agents](../../../AGENTS.md)、[context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md)、[src-workflow-schema](../roadguard/schemas/workflow.py)。

<a id="assistant-rule-versions"></a>
## 运行记录的规则版本

classification：`confirmed_project_fact`。citation_id：`rg-kb-assistant#assistant-rule-versions`。

本包钉住 demo-rules-v1，而运行配置或旧巡检冻结快照可以属于 demo-rules-v2 等其他版本。C 必须先检查任务/巡检的 rule_version，依据该记录的 decision_trace、审核/任务 history 及相符的规则证据解释；不能默默改用最新静态表格推导原决策。匹配的保存证据足够时才解释；缺少匹配证据时返回 insufficient_data，并要求提供对应记录/版本。版本不一致不等于记录错误，也不授权修改业务数据。

来源：[src-demo-rules](../../config/demo_rules.example.json)、[src-workflow-service](../roadguard/inspections/service.py)、[src-workflow-schema](../roadguard/schemas/workflow.py)。

<a id="assistant-evidence-limits"></a>
## 不支持的结论

classification：`confirmed_project_fact`。citation_id：`rg-kb-assistant#assistant-evidence-limits`。

本包没有真实训练指标、真实道路许可、运行方案、算法比较结果或测量工时。健康状态不证明模型/Google/GPT 已就绪；固定置信度不证明检测准确率；演示规则不证明工程严重度。GA 是否优于 Greedy 必须有同任务、同矩阵、同约束、多随机种子的实验记录。未知期限不能编造延期分钟数；没有成本模型不能宣称实际金额节省。

回答同时保留支持与不足：静态项目解释可以 supported，但需要缺失动态证据的具体数字/结论应 insufficient_data。引用相关稳定 section，并说明版本；来源没有提供的事实不得补写。

来源：[context-agents](../../../AGENTS.md)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)、[src-label-schema](../../model/label_schema.json)、[src-demo-rules](../../config/demo_rules.example.json)。
