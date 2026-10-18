# A → C 知识资料包

包 ID：`roadguard-a-knowledge`；版本：`a-knowledge-v7`；模块维护人：A。此包是可引用的项目资料，不包含 LLM、嵌入、索引、检索器或助手执行服务。

先读取 [manifest.json](manifest.json)，再按 documents 列表读取六份中文资料。文档路径相对本目录；sources/context_sources 的路径相对仓库根目录。引用形式固定为 `document_id#section_id`，对应文档中的显式 ASCII anchor；不要依赖自动生成的中文标题 anchor。引用应同时携带 package_version、document_version 及相关 scope/rule/label 版本，便于解释旧答案。

每个 section 的 classification 区分：`confirmed_project_fact` 是已记录的项目决定或当前可执行行为；`demo_assumption` 是明确未校准的演示参数/策略；`pending_decision` 是仍未确认的选项。项目约定可以已经确定而对应服务尚未实现，正文会明确区分。不能把分类为项目事实的“计划接口要求”描述成正在运行的功能。

v6 同步 demo-rules-v2 的项目工时决定。2026-10-18 的 v7 同步上传解码隔离修复的源码摘要，并纠正 qa-03 中“真实检测全部先审核”的过期要求：主框原始置信度 ≥0.60 自动建任务，低于阈值待审核。六份正文版本和业务规则保持不变；此维护更新不代表助手实现或全部 B/C 知识已更新，接入前仍需核对阶段描述与运行方案来源。参数经项目发起人确认不等于工程有效性获批，下面的 review 元数据仅说明资料包核对方式。

review_basis 为 `repository_consistency_review`：本轮 coding agent 代表 A 对照仓库源码/配置进行一致性核对，不代表 A 本人的人工签署、工程专家批准、道路许可或真实试验验证。manifest 明确记录 `human_or_expert_approval=false`。

sha256 使用文件原始 UTF-8 字节；仓库通过 .gitattributes 固定 LF。核验 documents、sources 和验收文件的摘要后再摄取。发现摘要/版本不一致应停止使用旧资料并由 A 更新包版本；规则变动还须更新规则版本及对应表格。context_sources 是显式不做摘要的可变背景文档，不能用它们代替带摘要的配置/代码事实。不要把上传图片、真实巡检数据库、凭据或运行方案复制进静态知识包。

[acceptance_cases.json](acceptance_cases.json) 提供十个未来助手验收题。`supported` 表示有静态依据支持所列解释，不表示已经执行修改；`insufficient_data` 表示问题需要包中没有的运行事实/实验/道路权限证据，须承认不足并指出缺少的材料。期望要点是验收要求，不是伪造的助手测试结果。

文档完整性测试为 `python -m pytest SystemCode/tests/test_knowledge_handoff.py -q`，验证来源摘要、引用 anchor、标签/演示映射与十个验收题。C 后续自行实现检索与引用，并以 B 的持久化方案事实回答动态路线问题。
