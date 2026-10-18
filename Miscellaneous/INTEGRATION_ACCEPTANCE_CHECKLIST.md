# RoadGuard 联调验收清单与 A 模块准备验收

2026-10-18 更新：A/B/C 现有模块已进行独立数据库的前后端联调，实际通过项、解码修复及助手/Google 未验收边界见[本次验收记录](INTEGRATION_ACCEPTANCE_20261018.md)。下文保留 2026-10-14 的 A 阶段基线，不能将当时的 B/C 未就绪描述当作当前进度。

日期：2026-10-14；清单版本：`integration-checklist-v1`；负责人：A。

规则依据：[业务规则定稿](BUSINESS_RULES_BASELINE.md)。接口依据：[API 契约](API_CONTRACT.md)与[返回字段说明](INSPECTION_RESPONSE_FIELDS.md)。当前范围：验收 A 的规则/工作流和交付样例；**B/C 尚未就绪，跨模块整合暂不执行**。清单中的预期不是已经完成的系统结果。

## 1. 验收条件与记录方法

| 项目 | 本轮要求 |
| --- | --- |
| 当前业务规则 | demo-rules-v2；P3/P2/P1＝60/120/240 分钟；原类别与严重度映射不变 |
| 当前接口 | a-workflow-v5；上传四字段；单展示框；主框 ≥0.60 自动建一个 Task |
| B 开发样例 | planning-synthetic-v2；10/15/20 任务及空队列/未知时长；没有矩阵或路线 |
| C 知识资料 | a-knowledge-v6；内容/引用/摘要验证，不代表助手已执行 |
| 测试隔离 | 自动测试用临时 SQLite/图片；手工 HTTP 用独立数据库和端口，不能污染常用数据库 |
| 模型边界 | 单元/HTTP 测试可注入明确标记的假检测器以控制阈值；真实模型质量必须另测，不能把 stub 输出称为模型效果 |
| 完成状态 | passed＝执行并有结果；failed＝执行不达预期；not_run＝未执行；blocked＝缺模块/参数/凭据；不将 blocked 算作通过 |

每次执行记录：用例编号、代码提交与未提交改动状态、规则/知识/模型版本、执行人和 UTC 时间、输入来源、请求 key、HTTP 状态、预期与实际、证据路径、pass/fail/block 原因。随机资源 ID 由本次响应提取，不复制别人机器或历史样例的 ID。

## 2. A 可立即执行的规则与 API 验收

以下条目均由 A 负责。测试入口相对仓库根目录；本轮实际执行结果单列在第 6 节，不以“已有测试文件”代替通过记录。

| ID | 输入/步骤 | 必须观察到的结果 | 自动证据入口 |
| --- | --- | --- | --- |
| A01 | 八类分别通过真实模式自动门槛（注入 0.60 检测） | 类别映射正确；P3/60、P2/120、P1/240；active、due_at=null；Task 详情、history、快照一致 | test_business_baseline.py::test_v2_eight_class_durations_reach_task_detail_and_snapshot |
| A02 | 注入 0.599999，审核纠正为八类中的每一类 | 审核前无任务；审核后使用目标类别 v2 时长；原检测和置信度保持，记录人工来源 | 同 A01 的 review_correction 参数 |
| A03 | 0.599999、0.60、0.600001；包含多个候选及低于 0.60 的 ranking_score | 原始主框 confidence 才是门槛；等号自动接受；不得用 ranking_score 或次框替代 | test_real_vision.py::test_real_primary_uses_inclusive_confidence_gate；test_single_box_workflow.py::test_gate_uses_primary_raw_confidence_not_best_score_or_ranking |
| A04 | 上传、详情、列表、幂等重放分别检查结构 | 上传恰好四字段；detection 单对象/null；其他接口 detections ≤1；原始全部候选仍存库 | test_single_box_workflow.py::test_http_auto_upload_get_list_replay_all_have_one_box_and_raw_db_is_unchanged |
| A05 | 无检测并尝试审核 | no_detection、task_id=null、版本不增；不能直接确认/驳回无检测巡检来建任务 | test_real_vision.py::test_real_no_detection_has_no_task_and_cannot_be_confirmed |
| A06 | 待审核分别 confirm、correct、dismiss | confirm/correct 建一个任务；dismiss 无任务；保留审核事实、原始证据和版本 | test_workflow.py::test_review_records_declared_fact_keeps_raw_detection_and_uses_explicit_mapping；test_workflow_api.py::test_dismiss_keeps_inspection_history_without_task |
| A07 | 相同上传 key 重试与并发重试；再用相同 key 改图片/元数据 | 相同请求 200 重放同资源；只推理/建任务一次；不同载荷 409，不覆盖原资源 | test_single_box_workflow.py::test_auto_task_is_exactly_once_including_concurrent_replay_and_restart；test_workflow.py::test_upload_key_reuse_with_changed_metadata_or_source_is_conflict |
| A08 | 审核/任务请求重试、同 key 改载荷、旧 expected_version | 幂等操作不重复修改；冲突 409；旧版本不能覆盖新状态 | test_workflow.py::test_review_replay_precedes_version_and_closed_state_validation；test_workflow.py::test_task_stale_write_and_key_payload_conflict |
| A09 | 修正任务标签及合法位置，提交无变化 patch | 标签修改重新映射冻结规则并记 history；真实输入变化 +1；无变化不增版本 | test_workflow.py::test_task_label_and_location_corrections_audit_changes_and_preserve_inspection；test_workflow.py::test_noop_task_patch_has_no_record_or_input_revision_change |
| A10 | 分别完成和取消任务，再查询/修改 | 历史详情保留；活动快照移除；每次真实变化 +1；终态不能重开 | test_workflow.py::test_terminal_task_preserves_history_and_cannot_change_again |
| A11 | v1 建立待审核/已接受记录，重启到 v2，审核/修正旧记录，再新上传 | 旧记录和 20/45/60 分钟历史语义保留；新任务用 v2；快照可混合版本；重放不需模型可用 | test_business_baseline.py::test_v1_records_retain_frozen_durations_after_v2_restart |
| A12 | JE/JW 内、外、边界；非法坐标/道路声明；任务位置改到范围外 | 边界覆盖规则一致；无效请求 422；不新增巡检、任务或图片，不改变已有记录 | test_geography.py；test_workflow_api.py::test_invalid_scope_and_metadata_leave_no_records_or_images；test_workflow.py::test_active_task_outside_scope_patch_does_not_modify_history_or_revision |
| A13 | JPEG/PNG、EXIF、损坏/不支持图片、超过大小/像素限制 | 成功图规范化；错误按契约 413/415/422；失败不残留新资源 | test_images.py；test_workflow_api.py::test_binary_size_and_stream_body_limits |
| A14 | 模型不可用或推理失败；数据库提交/图片保存失败 | 返回明确错误；不伪装为无检测或 demo；记录/任务/版本原子回滚，不留失败上传的新图片 | test_real_vision.py；test_workflow.py::test_database_commit_failure_rolls_back_upload_task_revision_and_new_image；test_images.py |
| A15 | 外部读事务保持时重启当前 schema；迁移被锁后重试；记录/图片重启读取 | 已初始化库只读启动成功；需写迁移仍遵守锁并可回滚；持久数据不丢失 | test_backend.py::test_restart_current_database_while_external_transaction_is_open；test_backend.py::test_migration_still_requires_lock_and_rolls_back_before_retry；test_workflow_api.py::test_restart_preserves_records_and_images |
| A16 | 查询空队列、超过 100 条、终态过滤、未知时长、旧 revision | 同一快照完整一致；null 保留；旧 revision 409；故障不是空队列 | test_task_query.py；test_task_query_api.py |
| A17 | 生成并核对 10/15/20 任务和知识包 | 样例 v2 时长、版本、摘要一致；不冒充道路验证；知识 v6 的规则表/引用/版本匹配 | test_planning_fixtures.py；test_knowledge_handoff.py |
| A18 | 在隔离服务运行已交付 HTTP 示例 | 四条演示巡检保留；审核、重放、完成/取消、快照和冲突按断言通过 | test_handoff_demo.py；SystemCode/examples/handoff_demo.py |

接口单元/组件检查不是 A/B/C 整合验收。A01/A02/A03 的受控检测器证明业务分流，不证明模型 Precision/Recall 达到 70%。真实图片的实际置信度不可人为填写，不能要求任意图片恰好输出 0.60。

## 3. 自动执行入口

使用已安装后端 CI 依赖的项目环境。下面的 `$acceptanceRun` 为每次运行建立独立、被 Git 忽略的证据目录，不覆盖旧记录：

```powershell
$acceptanceRun = Join-Path 'Dataset/acceptance' ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $acceptanceRun | Out-Null
$pytestTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('roadguard-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest SystemCode/tests -q --basetemp "$pytestTemp" --junitxml "$acceptanceRun/pytest.xml"
.\.venv\Scripts\python.exe SystemCode/contracts/planning/generate.py --check
.\.venv\Scripts\python.exe .github/scripts/check_repository.py
```

逐一确认每条命令退出码为 0，pytest 无失败；Windows 符号链接权限导致的 skip 单独记录。没有运行的用例不填 passed。pytest 的临时目录必须位于 Dataset 外，因为部分用例专门验证禁止将模型产出写到 Dataset 外；JUnit 证据仍保存到被忽略的 Dataset。测试使用独立临时数据库，用户已有 SQLite 不参与这些检查。

## 4. Swagger 与真实 HTTP 的手工复核

可选的手工复核使用单独终端、端口 8001 和新的目录；环境变量只在该终端设置，结束后关闭终端。若目录已有验收记录，应换一个新目录。

```powershell
$acceptanceRun = Join-Path 'Dataset/acceptance' ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $acceptanceRun | Out-Null
$env:ROADGUARD_DB_PATH = "$acceptanceRun/workflow.sqlite3"
$env:ROADGUARD_UPLOAD_PATH = "$acceptanceRun/uploads"
$env:ROADGUARD_DEMO_RULES_PATH = 'SystemCode/config/demo_rules.example.json'
$env:ROADGUARD_VISION_MANIFEST_PATH = 'disabled'
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8001
```

看到 `Application startup complete` 后，在另一个终端执行：

```powershell
.\.venv\Scripts\python.exe SystemCode/examples/handoff_demo.py --base-url http://127.0.0.1:8001 --confirm-demo-writes
```

该脚本会真正创建和修改隔离服务中的演示记录，不能对常用 8000 服务误执行。查看示例响应时必须保留 synthetic/demo 标记。手工打开 `http://127.0.0.1:8001/docs`，上传 JPEG/PNG，使用新的 Idempotency-Key（例如 `acceptance-high-001`）和 metadata：

```json
{"mode":"demo","scenario_id":"high_confidence","latitude":1.34,"longitude":103.72,"road_type":"public_motor_road"}
```

预期 201、accepted、一个 detection、非空 task_id；GET 该任务应为 pothole/medium/P2/**120** 分钟、rule_version=demo-rules-v2、due_at=null。新 key 配合 `low_confidence` 应待审核，`no_detection` 应无任务，`threshold_boundary` 验证合成值 0.60 的等号分支。审核参数使用本次详情中的 ID/版本。

真实模型手工测试应另开隔离实例，安装已发布权重并启用实际 manifest，metadata 改为 mode=real 且省略 scenario_id；保存实际响应/图片来源/模型哈希。错误分类、漏检和框偏移进入模型质量记录，不能通过更改输入置信度“修复”测试结果。本轮参数调整不要求重新训练模型。

## 5. B/C 就绪后才执行的整合验收

以下状态统一为 **blocked：B/C 尚未交付，本次不执行**。路径只是已约定的对接范围；不得创建返回固定成功数据的空接口来勾选通过。

| ID / 负责人 | 前置交付 | 步骤与验收条件 | 需要保存的证据 |
| --- | --- | --- | --- |
| BC01 / C+A | 上传、审核、任务页面 | 四字段上传可显示；详情取得审核 ID/版本；高置信度新任务可查；低置信度确认/纠正/驳回正确；页面状态与 API 一致 | 实际请求/响应、界面记录、任务快照 |
| BC02 / B+A | 队伍与规划输入服务 | 同一事务取活动任务和四队状态；停用队伍不分配；service_minutes 直接取保存值；未知值不变 0 | revision、队伍状态、输入快照 |
| BC03 / B | 基地车辆入口、允许道路、矩阵来源及约束 | 四队同 NUS-ISS 起点；基地至首任务计入行程；不可达明确处理；是否返基地/班次先确认 | 节点顺序、道路验证、同版矩阵、约束配置 |
| BC04 / B+A | Greedy/GA、方案持久化 | 同输入/矩阵/约束比较；合法任务不重复、不遗漏；不可分配保留原因；保存前检查 revision | plan_id、输入版本、分配/未分配清单、随机种子 |
| BC05 / A+B+C | 任务变化触发重算与旧方案提示 | 新增/完成/取消任务或停队后旧方案过期；不显示虚假重算成功；过期计算不能覆盖新输入 | 变化前后 revision、方案状态、失败反馈 |
| BC06 / C+B | 路线地图 | 显示四队、NUS-ISS、任务范围与停靠顺序；示意直线/真实道路区分；显示未分配和过期方案 | 方案与地图对应记录 |
| BC07 / C+A+B | GPT/RAG、方案查询 | 使用知识 v6 引用与实际 plan_id 事实解释；区分规则版本；证据不足说明不足，不编造节省/准确率 | 问答、引用、输入方案与版本 |
| BC08 / C+B | 助手调整预览/确认服务 | 停队请求先预览，经用户确认再调用 B；取消不执行；重复/过期确认正确处理 | 请求 ID、预览/确认/取消结果、规划版本 |
| BC09 / A+B+C | 全部上述模块 | 网络/模型/矩阵/助手故障可理解且不伪造成功；空任务、少于四任务、全部停队、10/15/20 场景完整检查 | 缺陷记录、恢复结果、端到端执行报告 |

## 6. 本轮执行记录

执行日期：2026-10-14；执行人：coding agent on behalf of A。代码基点 `21e17373749e43149b5c28ca3d214eb49f79ed40`，分支 `feature/a-business-rules-baseline`，含本轮未提交改动。规则/接口/知识/样例版本见第 1 节。本轮结果是本地验收，尚未推送 GitHub 或执行远端 CI。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| A01–A18 对应完整自动测试集 | passed：871 passed、1 skipped、0 failed，40.08 秒 | 本地 Dataset/acceptance/business-rules-v2-20261014/pytest-final.xml |
| 新增业务基线与兼容测试 | passed：8 类 × 自动接受/人工纠正共 16 例，加 1 例 v1→v2 重启兼容；包含于上述总数 | test_business_baseline.py 与同一 JUnit |
| 固定任务样例可复现 | passed：generate.py --check，全部字节与当前来源一致 | 本轮命令输出 |
| 仓库规范与文档链接 | passed：check_repository.py，203 个文件 | 本轮命令输出 |
| 隔离进程内 Uvicorn + 实际 TCP HTTP | passed：16 组响应断言；新建自动 P2/120 分钟任务，人工纠正后 P1/240 分钟任务 | 本地 Dataset/acceptance/business-rules-v2-20261014/http-results.json |

HTTP 证据时间为 `2026-10-14T01:45:40.580105+00:00`；使用显式 demo 场景和独立临时端口/数据库，真实模型禁用。结束时保留 4 条巡检、2 条已完成/取消的任务，活动快照为 0 条、input_revision=4；验收服务已关闭，未操作常用 8000 服务和数据库。

1 项 skip 为 Windows 符号链接权限限制；1 项 warning 为已有的 Starlette/httpx 弃用提示。首次全量运行将 pytest 临时目录置于 Dataset 内，导致“拒绝 Dataset 外输出”的测试前置条件不成立；改用 Dataset 外的独立临时目录后，全量重跑通过。首次失败记录保留为同目录 pytest.xml，最终结果以 pytest-final.xml 为准。

上述 Dataset 证据仅存本地，按仓库忽略规则不上传；组员应使用第 3 节命令生成自己的验收记录。自动测试的真实模式检测值由假检测器注入，HTTP 示例也采用合成检测，均不代表真实模型质量验证。

B/C 整合状态：blocked。真实模型质量验收：本轮 not_run；此前“Precision 与 Recall 同时超过 70%”尚未达成。
