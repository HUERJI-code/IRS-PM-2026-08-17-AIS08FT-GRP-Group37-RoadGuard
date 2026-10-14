# RoadGuard 业务规则定稿：课程模拟基线

日期：2026-10-14；负责人：A；基线编号：`business-baseline-v1`；运行规则版本：`demo-rules-v2`。

本次范围是业务规则、可复现开发样例和验收准备。B/C 尚未完成模块，四队规划、页面、地图和助手接入暂不执行。验收安排见[联调验收清单](INTEGRATION_ACCEPTANCE_CHECKLIST.md)。

## 1. 定稿依据与版本

项目发起人明确将预计维修时长定为 **P3＝60 分钟、P2＝120 分钟、P1＝240 分钟**；八类标签的严重度/优先级映射沿用当前配置，单主框置信度达到 0.60 自动建一个任务的约定不变。这里定稿的是课程模拟业务参数，不是工程测量结果或真实维修承诺。

- 唯一运行配置：[demo_rules.example.json](../SystemCode/config/demo_rules.example.json)。保持 `is_demo=true`、`status=demonstration_assumptions`，文件名和 `ROADGUARD_DEMO_RULES_PATH` 保持兼容。
- 历史参考：[demo-rules-v1.json](../SystemCode/config/rule_history/demo-rules-v1.json)。历史文件不自动加载，也不替换数据库中的冻结规则。
- HTTP 契约保持 `a-workflow-v5`，任务快照保持 `a-task-query-v1`，SQLite 结构保持 v2。仅规则内容、开发样例与知识资料更新。
- C 的知识包为 `a-knowledge-v6`；B 的固定任务样例为 `planning-synthetic-v2`。

## 2. 八类损伤与任务属性

| ID | label_key | 中文类别 | severity | priority | service_minutes | 模拟维修建议 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | longitudinal_crack | 纵向裂缝 | low | P3 | 60 | 检查并评估裂缝维修方法 |
| 1 | longitudinal_crack_wide | 宽纵向裂缝 | medium | P2 | 120 | 检查并评估裂缝维修方法 |
| 2 | transverse_crack | 横向裂缝 | low | P3 | 60 | 检查并评估裂缝维修方法 |
| 3 | transverse_crack_wide | 宽横向裂缝 | medium | P2 | 120 | 检查并评估裂缝维修方法 |
| 4 | alligator_crack | 龟裂（网状裂缝） | medium | P2 | 120 | 检查并评估路面维修方法 |
| 5 | alligator_crack_sunken | 下陷龟裂 | high | P1 | 240 | 检查并评估路面维修方法 |
| 6 | pothole | 坑洞 | medium | P2 | 120 | 检查并评估坑洞维修方法 |
| 7 | pothole_deep | 深坑洞 | high | P1 | 240 | 检查并评估坑洞维修方法 |

表中中文建议是配置内英文 `recommendation` 的说明，API 原字段不改名、不改语言。`reason` 明确记录演示假设。P1 比 P2、P3 更紧急；优先级是任务属性，不保证最终路线严格按 P1→P2→P3 排序，路线约束和优化目标由后续调度设计决定。

`service_minutes` 表示一个任务的模拟现场服务时长；**不是截止期限、响应时限、出发时间或行程时间**。行程分钟数另由 B 提供，规划时不能把服务时长当作行程。一个任务为 240 分钟，不因有四支队伍自动除以四；多队同时修同一个任务不在当前已实现流程中。

wide/deep/sunken 是数据集的视觉类别，不是毫米或厘米测量；没有利用框面积估算真实深度、道路结构或工时。模型置信度只参与接受/审核分流，不提高或降低严重度，也不直接缩放工时。

## 3. 当前分流、单框与任务创建

真实上传先按已发布模型的主框选择策略选定一个候选，再比较该框的原始 `confidence`：

| 输入情况 | inspection.status | task_id | 规划输入版本变化 |
| --- | --- | --- | --- |
| 无检测 | no_detection | null | 不变 |
| 主框 confidence < 0.60 | pending_review | null | 不变 |
| 主框 confidence ≥ 0.60，含等号 | accepted | 创建一个 active Task | 同事务 +1 |
| 审核确认/纠正 pending_review | accepted | 创建一个 active Task | 同事务 +1 |
| 审核驳回 pending_review | rejected | null | 不变 |

- 上传成功只返回 `inspection_id`、`status`、`detection`、`task_id`；detection 是单对象或 null。详情/列表/审核的 detections 数组最多一项，原始候选继续保存在数据库。
- 真实主框由 manifest 的 `area_quarter` 等既定策略选定，不因更换维修时长而改用优先级挑框。主框低于阈值时，另一个高置信度候选不自动替代它。歧义提示继续保留，但不额外阻断达标主框。
- 当前模型推理过滤值 0.20 与业务接受值 0.60 不同；未新增“低于 0.30 丢弃”规则。0.60 不是模型正确率保证。
- `/demo` 预览和显式 demo 上传保留已有合成案例语义：任一候选低于阈值即待审核；全部达标时按 priority、severity、service_minutes、confidence、ID 选择。预览 `ready_for_task` 不代表已创建任务。新规则使同一优先级的时长相同，因此原先 35/45 分钟的排序差异不再存在；后续按置信度和 ID 打破平局。
- 真实 Detection 的 is_demo=false；Inspection/Task 的 is_demo=true 表示其业务参数仍是模拟值。真实推理失败不回退成 demo 成功。

## 4. 审核、修改与历史一致性

1. 审核前 GET 巡检详情，取得 detection_id 和 record_version；上传四字段中不携带这两个值。
2. confirm 保留损伤类别；correct 使用审核指定类别映射任务，保留原检测标签/置信度与审核记录；dismiss 保留驳回记录。审核只接受 pending_review，不能将 no_detection 直接确认建任务。
3. 任务类别修正重新计算该类别对应的严重度、优先级和服务时长，不能由调用者直接任意改这些派生字段。
4. completed/cancelled 保留历史，退出活动快照；当前没有重开终态任务的接口。
5. 一个业务动作的重试复用同一幂等 key；更换请求内容必须换 key。重放不重复建任务、不重复递增 input_revision；上传重放 200，新建 201。
6. expected_version 防止覆盖别人更新的资源；input_revision 标识规划输入快照，两者用途不同。真实输入变化才增版本，纯读取、预览、无变化 patch 和重放不增版本。

**旧数据不批量迁移。** 规则在巡检创建时冻结。v1 巡检即使在 v2 发布后才审核，仍按其 v1 快照产生任务；旧任务类别修正同样使用原巡检的规则。新建巡检才使用启动时加载的 v2。活动快照允许同时包含 v1/v2 Task，B 应直接读取每条 Task 保存的 service_minutes，不拿最新配置统一重算。

旧版示例：v1 普通坑洞为 P2/45 分钟，深坑洞为 P1/60 分钟；新版分别是 P2/120、P1/240。历史响应样例与已有实验证据保留原版本，不篡改成新版结果。需要全部使用 v2 的演示应建立新的隔离数据库并通过正常流程创建新巡检。

## 5. 范围、空值和仍待决定的内容

- 任务仍限于冻结的 Jurong East/West 多边形与允许道路声明；NUS-ISS 是指定的区域外调度起点，不可直接当作区域内维修点。
- `due_at=null`：没有确定任务期限，不能用服务时长算截止时间或编造延误。
- 外部/旧版任务的 `service_minutes=null`：未知，不是 0；当前 v2 的八类默认规则全部有明确时长。
- 班次长度、是否返基地、队伍能力、截止期限、优化权重、GA 参数与实际基地车辆入口继续待 A/B 确认。`return_to_depot=null` 不能默认成 false。
- 本次不实施 crews/routing/assistant/frontend，不启动模型训练、Google 或 GPT 调用，也不声称联调或模型质量达标。

## 6. 发布与使用

规则启动时加载，更新配置后重启后端；若 PyCharm 配置了 ROADGUARD_DEMO_RULES_PATH，确认它指向 v2 配置。查看 Task.rule_version 和 decision_trace 中的版本核实实际生效，不能仅凭页面上的“最新”判断。

变更后先运行[验收清单](INTEGRATION_ACCEPTANCE_CHECKLIST.md)中的 A 检查。以后改变阈值、映射、工时或建议时新增规则版本，同步文档、知识包和固定样例，并验证旧记录兼容。保留 Dataset、运行数据库和上传图片的 Git 忽略规则。
