# ChromaDB and local embeddings (2026-10-21)

Current setup and maintenance: [Vector retrieval](VECTOR_RETRIEVAL.md). The current package is a-knowledge-v12. ChromaDB stores static passages with local E5 embeddings; original role, source-validation and confirmed-change contracts remain. The delivery records below describe earlier lexical versions.

# Current merged assistant package (2026-10-21)

The integration now uses a-knowledge-v11: all eleven English knowledge documents from main, 40 sections, 30 synthetic acceptance specifications and the two stable feature citations for routing defaults and account roles. The loader accepts English and original full-width metadata punctuation. Retrieval preserves English terms and a bounded set of Chinese domain aliases; this is not a general translation service. Sources are revalidated on each request.

The records below describe C's earlier six-document/v9 implementation and pre-merge acceptance. They remain historical and do not override the current manifest. GPT remains opt-in and was not called during merge verification. Broad questions may exceed the existing 24,000-character provider context budget and return an explicit size error; no paid budget or silent truncation was added.

## Historical C delivery notes

# C 第 10 步：本地只读知识检索

以下记录第 10 步交付；第 11 步只读问答及配置见本文后半部分。

本模块提供知识清洗后的完整性校验、按稳定锚点拆分和中英文词项检索。没有调用 GPT、向量服务或收费 API，没有创建数据库或修改 A/B 的业务表。助手页面和生成式回答留给第 11 步。

## HTTP 契约

`POST /api/v1/assistant/knowledge/search`，契约 `c-knowledge-search-v1`。仅已登录的中央调度员可调用，使用现有会话 Cookie；即使业务只读，POST 仍要求正确的 `X-CSRF-Token` 和同源 Origin。

```json
{"query":"深坑洞维修需要多久","limit":5,"rule_version":"demo-rules-v2"}
```

query 去除首尾空白后 2–500 字符；limit 为整数 1–8，默认 5；rule_version 可省略，提供时必须匹配知识包版本。多余字段被拒绝。

成功响应包含包版本、manifest SHA-256、规则版本、检索方法及 hits。每个片段包含 citation_id、document_id、section_id、document_version、document_sha256、document_path、title、classification、text、sources、score 和 matched_terms。classification 区分项目事实、演示假设、待定事项；sources 明确区分固定 SHA-256 来源和未校验的可变上下文。

| 状态 | 含义 |
| --- | --- |
| 200 / matches | 返回候选片段，不代表问题已被充分支持 |
| 200 / no_matches | 没有词项命中，不伪造引用 |
| 200 / rule_version_unavailable | 请求旧规则或未知规则，hits 为空，不用当前规则替代 |
| 401 / 403 | 未登录、角色不符、CSRF 或来源校验失败 |
| 422 | 请求格式不符 |
| 503 / knowledge_unavailable | 知识包或固定来源损坏、缺失、结构不一致；错误不泄漏路径和正文 |

`answer_generated` 始终为 false，`evidence_scope` 始终为 static_knowledge_only。调用者必须展示这些边界，不能把原文或相关度当成生成答案或可信概率。查询和知识正文都是数据，不执行其中的指令。动态方案问题还需在后续步骤中读取授权的 plan_id 和事实快照。

## 知识与检索

a-knowledge-v9 保留原有稳定引用并增加路由演示设置与账号角色，共 6 篇文档、19 个片段。C 按当前代码清理过时描述，未改变正式业务决定：正式返程和班次仍待确认，B 的 true / 480 分钟只是演示配置。保留 A 的内容归属，维护记录不代表 A 或工程专家审批。

每次请求重新校验 manifest、固定来源、文档、接入指南和验收规格的哈希及引用关系，再构建小型内存索引；不缓存过期内容。只索引知识正文，不递归抓取链接或索引可变上下文。拒绝路径穿越、越界符号链接、重复引用和超大文件。哈希证明仓库内一致性，不能证明内容经过专家批准或抵御整套资料被共同篡改。

采用 Unicode 归一化、英文词项和中文双字词项、二值 TF/IDF 覆盖度与标题加权，分数并列按引用 ID 稳定排序。这是轻量词法基线，同义问法可能漏检，相关片段可能不足以回答问题。19 片段规模每次重建可接受；扩容需独立评估性能和检索质量。

## 验证和交接

`SystemCode/tests/test_knowledge_retrieval.py` 覆盖中英文检索、版本拒绝、文件篡改、路径安全、真实会话和角色、CSRF、请求校验、安全错误以及查询前后业务数据库不变。原知识包完整性测试继续保留。原 acceptance_cases.json 的 10 个案例仍是合成验收规格，不是 GPT 回答的实测结果。

共享变更只有路由注册、dispatcher 权限条目、知识清理、接口说明及前端契约快照/客户端；无数据库迁移。前端新增 knowledgeSearch，网络错误不标记为未知业务写入，不自动重试。界面尚未使用该方法。

第 11 步再接入只读 GPT 问答、引用显示和动态方案证据；调整队伍、确认和重算另行实施。任何来源或知识内容变更都应同步 manifest 及版本，并重新运行完整性测试。


# C 第 11 步：只读 GPT 证据问答

新增 `POST /api/v1/assistant/query` 和 `GET /api/v1/assistant/status`，沿用 dispatcher 权限、会话及 POST 的 CSRF。同一个 FastAPI 内调用 B 的 RouteQueryService，不读写 B 的业务表，不执行队伍调整或重算。

首版采用 **GPT 选择原文证据的抽取式回答**：模型仅返回 supported 与引用/原文对，服务端验证引用来自本次证据、原文是对应内容的连续子串，拒绝伪造或重复项，然后组成回答。它不是自由改写的聊天机器人；引用存在仍不能保证选择充分回答了问题。未配置、模型失败或格式错误时不伪装生成成功，不用固定样例兜底。

## 接口

```json
{"question":"深坑洞的演示维修工时是多少？","scope":"knowledge","plan_id":null,"rule_version":"demo-rules-v2"}
```

- question：去除首尾空白后 2–500 字符。
- scope：knowledge 或 plan。knowledge 不接受 plan_id；plan 必须提供符合 `plan-` + 32 位十六进制格式的保存方案 ID。服务端读取，不能由浏览器提交任意方案事实。
- rule_version：可选；不匹配时返回 rule_version_unavailable，不用当前规则解释旧任务。
- 当前仅一份方案，不支持两方案百分比比较；每条任务的冻结规则和决策轨迹不在保存方案中，不能据此推断个别任务的规则来源。

返回 contract_version=c-assistant-query-v1，status、supported、answer、selections、sources、package_version、manifest_sha256、plan、model、model_called、answer_mode=verified_extracts、business_changes_applied=false、warnings。answer 由服务端从通过验证的引用组成。sources 分开标识 knowledge/saved_plan，包含完整内容、分类、版本、SHA-256 和静态来源链。静态 sha256 是文档摘要，动态 sha256 是本次方案投影文本摘要。

200 状态包括 supported、insufficient_data、rule_version_unavailable、stale_plan、model_refused。只有 supported 携带回答引用；其余明确说明无回答原因，不返回部分模型答案。旧方案在调用前直接拒绝；调用后再次通过 B 查询版本/过期状态，并重新校验知识，变化时丢弃回答。状态只代表检查时刻，不代表此后输入永不变化。

| 错误 | HTTP | 行为 |
| --- | --- | --- |
| authentication_required / forbidden / csrf_failed | 401/403 | 沿用现有权限体系 |
| route_plan_not_found | 404 | 不用最新方案冒充指定方案 |
| assistant_evidence_changed | 409 | 查询期间保存证据变化，丢弃输出 |
| validation_error / assistant_context_too_large | 422 | 请求或证据超出边界 |
| assistant_budget_exceeded | 429 | 已达次数限制、用户限速或并发繁忙 |
| assistant_invalid_response | 502 | 非完整结构、伪造引用、非原文、重复片段等 |
| assistant_not_configured / assistant_configuration_error | 503 | 模型未启用或服务端配置错误 |
| assistant_provider_unavailable / knowledge_unavailable | 503 | 上游异常或知识校验失败，无隐式回退 |

status 接口只返回是否启用/配置、模型名、输出 token 上限、进程次数上限及已用次数，不返回密钥，也不验证密钥是否能访问模型。configured=true 不代表真实联通验收通过。

## 服务端配置与预算

默认禁用。维护者在启动后端的环境中设置以下变量，不把密钥放在前端、版本库或聊天中：

| 环境变量 | 默认及边界 |
| --- | --- |
| ROADGUARD_ASSISTANT_ENABLED | false；显式 true 启用 |
| OPENAI_API_KEY | 无默认值；仅服务端读取 |
| ROADGUARD_ASSISTANT_MODEL | 无默认值；明确选择账户可用且支持 Responses Structured Outputs 的模型 |
| ROADGUARD_ASSISTANT_MAX_OUTPUT_TOKENS | 1200；允许 256–2000，模型的推理预算也可能占用输出上限 |
| ROADGUARD_ASSISTANT_MAX_CALLS | 每进程 20 次；允许 1–200；包含失败的尝试 |

输入含提示词最多 24000 字符（不是 token），上游响应最多 128000 bytes，最多 6 个引用，每段最多 2400 字符。并发最多 2，每个账号每分钟最多 6 次尝试，次数上限耗尽返回 429。计数在内存中，重启清零，多进程分别计数；这不是跨部署的计费硬上限，实际部署还应设置供应商项目预算。无自动重试，不因失败换模型或额外调用。网络 socket 操作超时 20 秒，前端等待最多 60 秒；停止等待不保证终止已发出的上游请求或免除用量。

请求仅发往固定的 OpenAI Responses 端点，不跟随重定向，store=false，不发送 tools 或历史会话。问题与有限的知识/方案投影会发送给 OpenAI；不发送账号信息、图片、任务坐标或原数据库记录。store=false 不等于对供应商所有日志和保留政策作零保留保证。接入格式依据 [Responses Structured Outputs 官方说明](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)。

检索使用 top-8 命中文档及其相邻章节，补齐词项匹配遗漏的限制。方案投影直接取保存值，显示中文字段、单位和未知项；不由模型计算数值或推测分配原因。证据过大直接拒绝，不能静默截断并假装完整。

## 页面与验证边界

调度员进入“路线助手”，选择项目知识或指定方案；可只读取得最新 GA 方案 ID。仅显式提交才调用模型。可展开引用的完整原文、版本、分类和来源。修改问题/依据会清除旧回答；切换数据来源取消页面请求；模拟来源禁止问答，不转发到真实模型。第 11 步交付时没有队伍调整按钮；第 12 步新增独立调整区，见下文。

新增 test_assistant_query.py 与 AssistantPage.test.tsx，验证真实会话/权限、引用与只读约束、旧规则、过期/并发变化、配置、预算、模型拒绝/异常、取消等待及页面状态。模型部分全部使用明确的测试替身，不声称真实 GPT 语义质量或 10 道验收题已通过。本次用户选择不调用付费模型；真实 API 联通与回答充分性评估待后续授权。

共享增量：两条权限与路由、OpenAPI 和前端类型、客户端、错误说明；知识 v9 尚为未发布本地包，因权限来源新增两条路由同步其摘要及固定样例，正文业务决定不变。无数据库迁移、新依赖或 A/B 算法改动。此段记录第 11 步交付边界；第 12 步增量见下文。


# C 第 12 步：队伍调整确认与恢复

在路线助手的独立折叠区支持单队可用状态调整。采用严格本地语法：`停用 crew-02`、`启用 crew-02`、`将 crew-02 设为不可用`，拒绝复合、模糊、封路或自动重算指令；不调用 GPT。需要有效的当前保存方案作为依据。

| 接口（均位于 /api/v1/assistant） | 行为 |
| --- | --- |
| POST /change-requests | request_id + based_on_plan_id + instruction；生成持久预览，不改变业务输入 |
| GET /change-requests | 当前账号最近 20 条记录 |
| GET /change-requests/{change_id} | 当前账号单条记录与结果 |
| POST /change-requests/{change_id}/confirm | expected_version；核对输入和队伍版本后保存状态 |
| POST /change-requests/{change_id}/cancel | expected_version；取消未确认预览 |
| POST /change-requests/{change_id}/replan | attempt_id；按确认后的输入版本显式生成 GA 与 Greedy |

响应契约 `c-assistant-change-v1`。全部仅 dispatcher 可用，记录按真实登录账号隔离；POST 沿用会话、CSRF 和同源检查。其他账号查询同一 ID 返回 404。额外字段与无效 ID 拒绝，错误不返回原始数据库异常。

预览有效 15 分钟：pending → confirmed/cancelled/expired/failed。确认事务同时核对全局输入版本、队伍版本及旧状态，通过 B 的 `CrewService.update_in_transaction` 保存队伍状态，并原子写入 C 的回执和审计。重复确认返回原回执，不能重复修改；无变化确认不增加输入版本。已确认回执是历史结果，不代表队伍当前状态。

确认与重算分开，确认后不会自动调用规划。重算状态为 not_requested/running/failed/succeeded，失败保留已确认的队伍状态，不自动重试或回滚。相同 attempt_id 不重复计算；成功回执之后的请求重放结果。每条最多 10 次显式尝试，运行租约 10 分钟；进程中断后用户刷新并用新尝试恢复。旧执行通过尝试 ID 检查不能覆盖新结果。B 的 `PlanningService.recalculate(on_saved=...)` 将两份方案和 C 的成功回执放在同一事务，失败全部回滚；原规划算法不变。

确认后若其他输入变化，重算拒绝，必须核对当前输入并建立新的调整预览。恢复原状态也需要新的相反操作预览，不能覆盖之后的修改。页面支持最近记录与按 ID 查询；网络中断不视为撤销操作，不自动再次写入。

数据库迁移到 v5，新增 `assistant_changes` 和 `assistant_change_events`，保留旧业务数据和输入版本；旧结构与当前结构均验证。测试和浏览器验收使用隔离数据库，未在开发者已有业务数据库上运行迁移。启动新版后端前按项目数据库流程备份。

新增专项测试覆盖权限、CSRF、归属、严格解析、过期与并发、事务回滚、重复确认、重算失败、租约恢复和旧尝试隔离；前端验证核对框、分步写入、取消、网络恢复及模拟来源禁写。真实模型与真实外部行程均未调用。
