# 单框响应、60% 自动建任务与字段说明

日期：2026-10-13；负责人：A；契约 a-workflow-v5；API 0.8.0。

## 当前行为

按项目发起人确认，真实模型上传先按现有主损伤策略选一个框，再使用该框的**原始 confidence**：

| 条件 | 巡检状态 | task | 规划输入 |
| --- | --- | --- | --- |
| 主框 confidence ≥ 0.60，包括恰好 0.60 | accepted | 自动创建一个 active 任务 | input_revision 加 1 |
| 有检测但主框 confidence < 0.60 | pending_review | null，等待确认/纠正/驳回 | 不变 |
| 无检测 | no_detection | null | 不变 |

上传仅返回 inspection_id、status、detection、task_id；detection 是单个对象，无检测为 null。详情、列表及审核里的 detections 保持数组格式，但最多一个元素，无检测是 []。所有接口和幂等重放选择同一个框：已接受记录返回 selected_detection_id 对应框；其余返回主建议；旧记录无建议则按最高置信度选择。完整原始框只保存在数据库 InspectionRecord 中，不在 HTTP 中重复返回。

默认选框策略仍为 `area_quarter`：confidence × 框面积占整图比例的四次方根。自动接受比较 confidence，不比较 ranking_score；其他候选分数与 ambiguous 不覆盖这一已确认分流。不额外强制 YOLO 的 max_det=1，否则会在主框排序前丢失证据。旧 manifest 没有主策略时使用最高置信度。

0.60 来自 [demo_rules.example.json](../SystemCode/config/demo_rules.example.json) 的 confidence_threshold；更改配置须更新规则版本并重启。推理过滤仍是发布 manifest 的 0.20。因此通常 0.20～0.60 进入审核，没有新增“低于 0.30 丢弃”的规则。0.60 是业务触发阈值，不是模型准确率保证；维修工时、严重度和优先级仍是演示假设。

模型权重、训练保存点与原始数据不变，没有启动训练。原巡检不重新推理、不自动补建任务；用旧 Idempotency-Key 重放仍返回原记录。要应用新规则测试图片，请使用新 key。

## Swagger 上传

重启后端，在 `/docs` 找到 `POST /api/v1/inspections`，点击 Try it out：

- idempotency-key：`single-box-test-001`（每次新测试换 key）。
- image：JPEG/PNG 文件，最多 8 MiB、2000 万像素。
- metadata：粘贴下面 JSON，不传 scenario_id。

```json
{
  "mode": "real",
  "latitude": 1.3405,
  "longitude": 103.706,
  "road_type": "public_motor_road"
}
```

该坐标用于 Jurong 范围内的流程测试，不是照片拍摄位置的证据。新请求成功返回 201；相同内容和 key 重放返回 200，内容不同但 key 相同返回 409。

## 上传的四个字段

| 字段 | 含义 |
| --- | --- |
| inspection_id | 巡检 ID，用于查询详情 |
| status | accepted 已接受；pending_review 待审核；no_detection 无检测；旧记录重放也可能为 rejected |
| detection | 一个检测对象，或 null；仅含 label、confidence、bbox_xyxy、image_width、image_height |
| task_id | 自动创建或人工接受后关联的任务 ID；未创建为 null |

完整当前样例：[real-upload-example.json](../SystemCode/contracts/workflow/real-upload-example.json)。detection 的五个字段分别表示类别英文键、原始置信度、原图像素框坐标、图片宽度、图片高度；不附带模型来源和审计字段。

详情查询：`GET /api/v1/inspections/{inspection_id}` 返回下文 inspection 字段，直接位于 JSON 顶层，没有 inspection 包装。`GET /api/v1/tasks/{task_id}` 返回完整任务。审核前从巡检详情取得 detection_id 和 record_version。

上传新建是 HTTP 201，重放是 HTTP 200；两者成功体都只有上述四个字段，不再带 replayed 或 input_revision。读取规划版本使用 `GET /api/v1/tasks/snapshot`。错误响应保持 code/message/details。

## 审核响应的顶层字段

以下完整包装用于审核结果；上传已改为上面的精简格式。

| 字段 | 含义 |
| --- | --- |
| inspection | 本次巡检记录，包括图片、检测、位置、决策和历史 |
| task | 关联的维修任务；未接受时 null。任务后来完成/取消后仍可返回关联历史 |
| input_revision | 全局规划输入版本，任务新增、实际修改、完成或取消会递增；不是任务数量 |
| planning_input_changed | 这次请求是否实际改变规划输入；重放为 false，不表示已重新计算路线 |
| replayed | 是否复用了同一幂等请求的已有记录；true 时没有重新推理或重复建任务 |

## 巡检详情字段（以及审核结果中的 inspection）

| 字段 | 含义 |
| --- | --- |
| inspection_id | 巡检唯一 ID |
| image_url | EXIF 归正、去 metadata 后的原尺寸 RGB PNG 地址；相对后端根地址 |
| annotated_image_url | 画框图地址，目前 null；Swagger 不直接画框，前端可用 bbox_xyxy 绘制 |
| latitude | 上传的 WGS84 纬度 |
| longitude | 上传的 WGS84 经度 |
| detections | 返回给用户的检测数组，0 或 1 条；字段见下表 |
| selected_detection_id | 已接受用于创建任务的检测 ID；pending_review 通常为 null |
| status | no_detection 无检测；pending_review 待审核；accepted 已接受并关联任务；rejected 人工驳回。accepted 不代表维修已完成 |
| task_id | 关联任务 ID；未产生任务为 null |
| decision_trace | 判定过程/规则原因的列表，供显示与追查 |
| is_demo | 当前 true 表示业务场景、工时等是课程模拟，不等于模型使用假数据 |
| created_at | 创建时间，UTC ISO 8601；Z 表示 UTC |
| updated_at | 此巡检最近修改时间 |
| record_version | 本巡检的并发控制版本；审核请求的 expected_version 使用它 |
| mode | real 为真实模型推理；demo 为指定的合成检测案例 |
| demo_scenario_id | demo 案例名称；real 为 null |
| model_version | 本次检测使用的模型版本标识 |
| model_weights_sha256 | 权重文件 SHA-256，用于核对实际模型；demo 为 null |
| model_manifest_version | 模型清单格式版本，目前 real 为 roadguard-model-v1；不是训练轮数 |
| primary_suggestion | 初次上传的主框排序快照，见下表；旧记录或无主策略时可为 null |
| auto_acceptance | 自动接受的策略快照，见下表；低分待审核、人工接受和旧记录为 null |
| image_width | EXIF 归正后原图宽度，像素 |
| image_height | EXIF 归正后原图高度，像素 |
| scope_version | 本次位置校验使用的 Jurong 边界数据版本 |
| road_type | 道路类型，目前 public_motor_road |
| road_type_source | 当前 user_declared，表示调用者声明，道路属性未经自动核验 |
| review_history | 人工审核历史；自动创建任务时为空数组 |

## detections[0] 字段

| 字段 | 含义 |
| --- | --- |
| detection_id | 此次模型检测的唯一 ID，审核时传入 |
| class_id | RDD2022ES 类别编号，0～7 |
| label | 类别英文键，对应 class_id |
| confidence | 原始模型置信度，0～1；0.60 表示 60%，不等于实际正确率 |
| bbox_xyxy | [左上角 x, 左上角 y, 右下角 x, 右下角 y]；归正后的原图像素坐标，不是 0～1 比例 |
| image_width | 检测对应原图宽度，像素 |
| image_height | 检测对应原图高度，像素 |
| model_version | 产生此检测的模型版本 |
| is_demo | real 检测是 false；合成检测是 true |

类别映射：0 longitudinal_crack 纵向裂缝；1 longitudinal_crack_wide 宽纵向裂缝；2 transverse_crack 横向裂缝；3 transverse_crack_wide 宽横向裂缝；4 alligator_crack 龟裂；5 alligator_crack_sunken 下陷龟裂；6 pothole 坑洞；7 pothole_deep 深坑洞。宽度/深度是训练标签含义，不代表已做工程测量。

## primary_suggestion 与 auto_acceptance

| 路径 | 含义 |
| --- | --- |
| primary_suggestion.policy_version | 选框策略版本，目前 single-damage-v1 |
| primary_suggestion.strategy | 排序方法，默认 area_quarter |
| primary_suggestion.threshold | 模型候选过滤阈值，默认 0.20；不是自动建任务的 0.60 |
| primary_suggestion.detection_id | 初次上传推荐的检测 ID；无候选为 null。人工后来选其他框时可能与返回框不同 |
| primary_suggestion.ranking_score | 选主框的排序分数；无候选为 null；不是置信度或正确概率 |
| primary_suggestion.ambiguous | 是否存在分数接近的其他类别/相离区域；保留提示，不阻止达到阈值的主框自动建任务 |
| primary_suggestion.competing_detection_ids | 主框及竞争检测的 ID；可能指向只在内部保留的候选，不附额外框；无歧义为 [] |
| auto_acceptance.policy_version | 自动接受规则版本，目前 single-primary-auto-v1 |
| auto_acceptance.confidence_threshold | 该任务自动创建时冻结的实际阈值，默认 0.60 |

## decision_trace[] 与 review_history[]

| 路径 | 含义 |
| --- | --- |
| decision_trace[].code | 机器可读的决策代码，如 real_primary_auto_accepted、real_primary_review_required、no_detection |
| decision_trace[].message | 该步骤的文字解释 |
| decision_trace[].rule_version | 本步骤使用的业务规则版本 |
| decision_trace[].is_demo | 当前 true，业务依据仍为演示 |
| review_history[].request_id | 人工审核请求的幂等 ID |
| review_history[].action | confirm 确认；correct 修正类别；dismiss 驳回 |
| review_history[].recorded_at | 审核记录时间，UTC |
| review_history[].detection_id | 人工选择的检测 ID；驳回为 null |
| review_history[].original_damage_label | 被选择检测的原始类别；驳回为 null |
| review_history[].corrected_damage_label | 修正后的类别；没有修正时 null |
| review_history[].note | 调用者备注；未填为 null |
| review_history[].rule_version | 审核所使用的冻结业务规则版本 |
| review_history[].actor_source | user_declared_unverified，操作身份未认证 |

## task 字段

task=null 时不存在下面的子字段。

| 字段 | 含义 |
| --- | --- |
| task_id | 维修任务唯一 ID |
| inspection_id | 来源巡检 ID |
| latitude | 任务当前纬度；允许通过任务修改接口修正 |
| longitude | 任务当前经度 |
| damage_label | 最终用于派工的损伤类别；可与原模型类别不同 |
| severity | low/medium/high 严重度，来自冻结规则 |
| priority | P1/P2/P3 优先级，P1 最高，来自冻结规则 |
| service_minutes | 预计维修分钟数；当前是演示估计，null 表示未知，不是零 |
| created_at | 任务创建时间，UTC |
| due_at | 任务期限；目前 null，未定义期限 |
| status | active 活动任务；completed 已完成；cancelled 已取消；只有 active 进入规划输入 |
| rule_version | 计算此任务类别映射、工时、优先级的规则版本 |
| is_demo | 当前 true，任务属于课程模拟维修业务 |
| updated_at | 任务最近修改时间 |
| record_version | 任务自己的并发版本，修改任务时用作 expected_version；不等于巡检版本 |
| repair_recommendation | 规则生成的维修建议文字 |
| history | 创建与修改的审计记录 |

## task.history[] 字段

| 字段 | 含义 |
| --- | --- |
| request_id | 创建/修改任务的幂等请求 ID；自动创建时来自上传 Idempotency-Key |
| action | created 创建；updated 修改 |
| recorded_at | 此操作时间 |
| changed_fields | 本次改变的字段名称列表 |
| before | 操作前的业务值快照；初次创建为 null |
| after | 操作后的业务值快照 |
| actor_source | system_confidence_policy 真实主框自动接受；system_demo_rules 合成案例自动接受；user_declared_unverified 人工声明操作 |

before/after 的完整字段为 status、latitude、longitude、damage_label、severity、priority、service_minutes、rule_version，含义与上面的 task 同名字段一致。

## 实际样例与验收

[real-upload-example.json](../SystemCode/contracts/workflow/real-upload-example.json) 来自 v5 隔离数据库的真实模型 HTTP 验收；图片为此前下载的磨损路面照片，检测置信度约 0.603604，因此自动创建一个演示任务。[real-auto-task-example.json](../SystemCode/contracts/workflow/real-auto-task-example.json) 保留为 v4 的历史完整响应示例。样例 ID 和 image_url 属于当时的临时数据库，不能在另一台机器上直接查询。它证明接口分流有效，不是专家标注或模型准确率证明。

另验证一张主框约 0.457828 的照片返回一框待审核（内部保留四框），以及街景图无检测时上传 detection=null、详情 detections=[] 且不建任务。检查幂等重放、关闭模型后重启读取和活动任务快照；v5 运行证据保存在被忽略的 Dataset/compact-upload-v1 中，v4 证据位于 Dataset/single-box-auto-v1-verified。

v5 本轮全量 `python -m pytest SystemCode/tests -q`：851 passed、1 skipped（Windows 链接权限）；仓库检查与 `git diff --check` 通过。覆盖四字段上传、详情查询、0.60 边界、多个候选时只比较主框原始置信度、歧义提示、并发防重复建任务、事务失败回滚、查询/审核/重放的单框投影、旧记录读取及知识包版本与来源完整性。上述真实模型测试使用隔离数据库，没有改动用户现有巡检和任务。
