# 演示规则与置信度分流

document_id：`rg-kb-demo-rules`；document_version：`1`；owner：`A`。

<a id="demo-rule-table"></a>
## 精确演示映射

classification：`demo_assumption`。citation_id：`rg-kb-demo-rules#demo-rule-table`。

当前规则版本 `demo-rules-v1`，`is_demo=true`，status 为 `demonstration_assumptions`。下表是集中配置的项目演示假设，未经过真实模型校准或工程工时测量，不用于指挥真实维修；维修建议也只是演示评估提示。

| label_key | 演示 severity | 演示 priority | 演示 service_minutes |
| --- | --- | --- | --- |
| longitudinal_crack | low | P3 | 20 |
| longitudinal_crack_wide | medium | P2 | 35 |
| transverse_crack | low | P3 | 20 |
| transverse_crack_wide | medium | P2 | 35 |
| alligator_crack | medium | P2 | 45 |
| alligator_crack_sunken | high | P1 | 60 |
| pothole | medium | P2 | 45 |
| pothole_deep | high | P1 | 60 |

来源：[src-demo-rules](../../config/demo_rules.example.json)、[src-label-schema](../../model/label_schema.json)。

<a id="demo-gate-selection"></a>
## 分流与单候选选择

classification：`demo_assumption`。citation_id：`rg-kb-demo-rules#demo-gate-selection`。

演示阈值 `confidence_threshold=0.60`：无检测是 `no_detection`；任一检测低于阈值就整体 `pending_review`，保留全部检测且没有候选；全部大于等于阈值才 `ready_for_task`。0.60 达标、0.5999 待复核。高低混合不能丢弃低框后自动接受。预览的 ready_for_task 只是候选计算结果，不表示巡检已保存、任务已入队或路线已经生成。

`selection_strategy=priority_severity_duration_confidence_id`：先 P1→P2→P3，再 high→medium→low，再已知维修分钟数由长到短（null 排后），再置信度由高到低，最后 detection_id 字典序。输入顺序不影响结果，全部检测仍保留。例如 0.90 的 pothole_deep 先于 0.98 的 longitudinal_crack，因为演示 P1 优先于 P3。每次巡检至多创建一个任务也是演示策略，尚非正式多损坏派工规则。

来源：[src-demo-rules](../../config/demo_rules.example.json)、[src-rule-service](../roadguard/rules/service.py)、[src-workflow-service](../roadguard/inspections/service.py)。

<a id="demo-null-provenance"></a>
## 未知值与来源

classification：`demo_assumption`。citation_id：`rg-kb-demo-rules#demo-null-provenance`。

未知 service_minutes 用 null，不用零；配置当前八类工时都是演示分钟数。任务 due_at 当前保持 null，不生成期限或延期指标。巡检冻结完整规则快照，审核和任务标签修正继续使用该快照，而不是重启后新配置。引用检测时保留 Detection 的 model_version/is_demo，引用决策时读取 Inspection 的 decision_trace，引用任务时保留 Task 的 rule_version/is_demo；不能假设 Task 自带模型版本或完整决策过程。上传图片不改变检测仍为指定合成案例这一事实。

本包静态表格只解释 demo-rules-v1；运行记录可能使用覆盖配置的其他版本。不能用本包或最新规则表重算/解释不同版本的旧任务，须依据该记录保存的规则版本、decision_trace 和 history；没有相符证据时承认 insufficient_data。

来源：[src-demo-rules](../../config/demo_rules.example.json)、[src-workflow-service](../roadguard/inspections/service.py)、[src-workflow-schema](../roadguard/schemas/workflow.py)。
