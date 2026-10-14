# 第 5 步：模拟检测与业务规则

日期：2026-10-12；负责人：A。此步实现可运行的检测与规则预览，已被[第 6 步持久化流程](INSPECTION_REVIEW_TASK_WORKFLOW.md)复用。以下 `/demo` 接口输入是明确选择的合成案例，不读取图片像素，不调用 YOLO、Google 或 GPT；仅返回候选，不创建巡检/任务或更新规划版本。第 6 步另有上传与保存接口。

## 演示规则与正式规则的区别

唯一规则配置为 [demo_rules.example.json](../SystemCode/config/demo_rules.example.json)。当前版本 `demo-rules-v2`，`is_demo=true`，`status=demonstration_assumptions`。2026-10-14 项目发起人定稿模拟工时 P3/P2/P1＝60/120/240 分钟，沿用原严重度/优先级映射及已确认的 `0.60` 阈值；详见[业务规则基线](BUSINESS_RULES_BASELINE.md)。这些值用于课程模拟，未经过真实场景阈值校准或工程工时测量，RDD2022ES 标签不提供这些业务参数。

| 数据集标签 | 演示严重度 | 演示优先级 | 演示维修分钟数 |
| --- | --- | --- | --- |
| longitudinal_crack | low | P3 | 60 |
| longitudinal_crack_wide | medium | P2 | 120 |
| transverse_crack | low | P3 | 60 |
| transverse_crack_wide | medium | P2 | 120 |
| alligator_crack | medium | P2 | 120 |
| alligator_crack_sunken | high | P1 | 240 |
| pothole | medium | P2 | 120 |
| pothole_deep | high | P1 | 240 |

这张表描述当前示例配置；改动以配置为准，并同步本文。建议与理由也保存在配置中，均说明模拟性质；不用于指挥真实维修。配置允许未知时长为 `null`，不允许以 0 代替未知值。未定义任务期限，不生成期限或逾期指标。

配置必须完整覆盖中央标签字典中的八个 `label_key`；缺失/额外类别、重复 JSON 键、非法优先级、布尔/字符串数值及非有限数字均拒绝。`ROADGUARD_DEMO_RULES_PATH` 可覆盖配置路径；相对路径以仓库根目录解析。配置在启动时读取，修改后重启并更新 `rule_version`；错误配置使启动失败，不悄悄回退。

## 分流与候选选择

本节描述 stateless demo 预览和显式 demo 上传。真实上传使用已发布模型选定的单主框比较 0.60，行为见[业务基线](BUSINESS_RULES_BASELINE.md#3-当前分流单框与任务创建)；不能把 demo 的多候选门槛套用到真实上传。

1. 没有检测：`no_detection`，候选和选中 ID 均为 `null`。
2. 任意检测的置信度 **小于** 阈值：`pending_review`。高低置信度混合时也保留所有检测并整体等待审核，不丢掉低置信度框后自动接受。
3. 所有检测均 **大于等于** 阈值：`ready_for_task`，计算规则并选出一个候选。该状态表示规则计算完成；不是已接受、已入队或已经通过地理校验。

多个检测先按 P1、P2、P3，再按 high、medium、low，再按已知维修时长从长到短、未知时长排后，再按置信度从高到低，最后按 `detection_id` 字典序选择。前面的条件优先，输入列表顺序不影响选中结果。所有检测仍返回，避免丢失其他损坏。整个排序策略同样是演示假设，不能代替正式多检测业务决策。

`decision_trace` 保留演示来源、置信度分流、各检测的规则理由和选取策略，每条都携带规则版本。稳定代码为 `demo_assumptions`、`no_detection`、`confidence_review_required`、`confidence_gate_passed`、`rule_mapping`、`candidate_selected`；调用方按代码判断，不解析自然语言说明。

## 如何运行

先按[后端说明](../SystemCode/backend/README.md)安装并启动。打开 `http://127.0.0.1:8000/docs`，使用以下两个演示接口：

- `GET /api/v1/demo/scenarios`：列出七个案例、检测器版本和模拟图像尺寸。
- `POST /api/v1/demo/assessments`：提交 `{"scenario_id":"high_confidence"}`，运行模拟检测器与规则服务。

PowerShell 示例：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/demo/scenarios
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/demo/assessments -ContentType 'application/json' -Body '{"scenario_id":"high_confidence"}' | ConvertTo-Json -Depth 10
```

| scenario_id | 固定检测内容 | 默认规则下的结果 |
| --- | --- | --- |
| high_confidence | pothole，0.96 | ready_for_task，medium / P2 / 120 分钟 |
| low_confidence | pothole，0.42 | pending_review，无候选 |
| no_detection | 空检测列表 | no_detection，无候选 |
| multiple_detections | 0.98 的纵向裂缝与 0.90 的深坑洞 | 选择 P1 的深坑洞，不仅看最高置信度 |
| mixed_confidence | 0.96 的坑洞与 0.42 的深坑洞 | pending_review，保留两个检测 |
| threshold_boundary | pothole，0.60 | ready_for_task，验证阈值等号 |
| below_threshold | pothole，0.5999 | pending_review |

案例置信度是固定值，名称描述默认 0.60 阈值。覆盖配置后结果可能改变，响应携带实际 `confidence_threshold` 与 `rule_version`。全部检测采用 640×480 合成图像坐标，未提供可下载的真实图片或标注图片。相同案例重复请求返回相同结果，列表和对象是独立副本；案例 ID 不是持久化巡检或任务 ID。

## 对接接口与边界

- `DemoDetector.detect(scenario_id)` 返回公共 `Detection` 列表，空结果也由 HTTP 响应中的 `model_version`、`is_demo` 和图像尺寸明确来源。更换模型需要显式实现适配，不存在真实模型失败后自动使用模拟检测的逻辑。
- `RuleService(policy).evaluate(detections)` 返回公共 `RuleAssessment`，只处理传入快照，不进行数据库写入。内部输入也重新校验标签、框、重复 ID 和同图尺寸。
- `RuleCandidate` 提供损坏标签、严重度、优先级、时长、维修建议、规则版本与演示标记。它没有 task_id、位置和创建时间；B 应继续使用 Task 契约，不能把候选直接当作可规划任务。
- 第 6 步负责图片/位置校验、巡检保存、人工确认/纠正/驳回、任务幂等创建和同事务版本递增。人工确认不能通过伪造置信度为 1.0 实现，需明确记录审核事实后复用标签映射。
- 原有第 3 步固定 JSON 是 `a-dto-v1` 的独立快照，使用 `demo-unconfirmed-v1`；当前在线演示使用 `demo-rules-v2`，不把旧快照当作规则配置加载。

新增 DTO 与错误码见[统一接口契约](API_CONTRACT.md)。本步不校验 Jurong 道路范围、不存储任务、不生成四队方案，不据此声称完整项目流程或检测准确率已验证。

## 验证入口

仓库根目录运行 `python -m pytest SystemCode/tests -q`。测试覆盖模拟案例的确定性与副本隔离、八类规则、阈值和配置边界、多检测排序、未知时长、规则版本、HTTP 错误、重复预览不写库/不增版本、启动配置覆盖，以及故障不会伪装成成功。规则配置和数据格式改变时必须同时维护相应测试。
