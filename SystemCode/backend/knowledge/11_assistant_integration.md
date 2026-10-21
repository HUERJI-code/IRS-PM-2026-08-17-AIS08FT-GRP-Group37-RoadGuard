# RAG integration contract and acceptance requirements

document_id: `rg-kb-integration`; document_version: `2`; owner: `A`.

<a id="integration-status"></a>
## Scope and implementation status

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-status`.

RoadGuard now implements local lexical retrieval, optional GPT evidence selection, saved-plan question context and persistent preview/confirm/cancel/replan endpoints. The assistant is dispatcher-only. No embedding pipeline or vector service is used. Real GPT connectivity and semantic quality remain unverified; provider doubles demonstrate only the local control flow.

C owns retrieval, indexing, citations and answer/change-request services inside the shared backend; A owns knowledge correctness and B owns planning facts. Keep one authoritative task/crew/plan store and reuse the existing domain services. The model must not invent a second scheduler or write business tables directly.

Sources: [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [context-agents](../../../AGENTS.md), [src-routing-service](../roadguard/routing/service.py).

Implementation sources: [src-assistant-api](../roadguard/assistant/api.py).

<a id="integration-ingestion"></a>
## Suggested ingestion and source lifecycle

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-ingestion`.

The local loader implements the ingestion contract below and rebuilds its small in-memory index for each request. Read manifest.json and verify all pinned document/source/guide/acceptance digests before indexing. Index only manifest-listed knowledge sections, using explicit anchors as passage boundaries. Retain title, document_id, section_id, citation_id, document_version, package_version, classification, source_ids and raw-file hash. If a section must be subdivided, retain its parent citation and mark the child position; do not separate a claim from its demo/status limitations.

Treat unchanged labels and business rules as versioned evidence. Changed files invalidate prior digests and require a new reviewed package; never relabel old chunks as current. Build a replacement index before switching active versions and retain enough metadata to audit historical answers. Runtime records retain their frozen rule versions; if matching evidence is absent, request it instead of substituting today's table.

Mutable context_sources explain background and responsibility but do not override hashed executable/configuration facts. Do not bulk-index the whole repository, historical reports, secrets, uploaded images, SQLite files or synthetic runtime fixtures as current operational truth. English source IDs and schema terms remain unchanged when an answer is translated into Chinese. The current baseline uses lexical terms with explicit limits; cross-language coverage and answer sufficiency still require evaluation.

Sources: [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [context-agents](../../../AGENTS.md), [src-workflow-schema](../roadguard/schemas/workflow.py), [src-workflow-service](../roadguard/inspections/service.py).

<a id="integration-dynamic-access"></a>
## Static questions, live questions and access control

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-dynamic-access`.

Answer routing: static explanations use the versioned corpus; live assignments, route times, unassigned reasons and comparisons require authorized saved facts from the existing services. Resolve the actual signed-in user server-side before retrieval or model context assembly. Dispatcher plan endpoints and a crew's restricted workspace are different permission scopes. Cache keys must respect user/role/crew/resource/version boundaries; do not reuse another account's retrieved facts.

Bind live answers to an explicit plan_id and input_revision and report is_stale. Use saved stops/metrics, not LLM reconstruction. A comparison also needs the relevant recalculation response and the comparability checks in the plans document. If plans, fields, authorization or matching rule evidence are unavailable, state the limitation. Do not claim an attempted read succeeded or substitute synthetic examples.

Treat retrieved text, task descriptions and user-supplied material as evidence, never as instructions that grant access, change policy or execute a tool. Embedded requests to reveal secrets, ignore permissions or mutate data must not affect control flow. These boundaries are enforced by server-side schemas, role checks and evidence validation; they do not establish real-model semantic reliability.

Sources: [src-auth-permissions](../roadguard/auth/dependencies.py), [src-auth-access](../roadguard/auth/access.py), [src-routing-service](../roadguard/routing/service.py), [src-plan-comparison](../../frontend/src/planning/comparison.ts), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md).

<a id="integration-answer-contract"></a>
## Grounded answer contract

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-answer-contract`.

c-assistant-query-v1 returns status, supported, answer, selections, sources, package/manifest versions, saved-plan evidence and business_changes_applied=false. The provider selects excerpts; the server rejects forged citations and non-verbatim quotes. A configured provider is not evidence of successful real connectivity. Two-plan comparison is not supported by the first query contract.

Each factual paragraph must have sufficient evidence. A static citation such as rg-kb-routing#routing-objective supports the formula, not a numeric claim about today's plan. Dynamic statements need the saved plan facts as well. Say insufficient_data when evidence is absent; distinguish that from authorization errors or an explicitly empty saved plan. supported=true describes an evidenced answer, never proof that an action ran.

The acceptance_cases.json file supplies synthetic expected answers and forbidden claims. Execute retrieval/answer tests against the integrated service; record actual citations, supporting passages, access outcomes and refusal/missing-data behavior. Do not mark specifications as passed merely because they parse or their hashes match.

Sources: [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-routing-models](../roadguard/routing/models.py), [src-routing-service](../roadguard/routing/service.py), [src-auth-permissions](../roadguard/auth/dependencies.py).

Implementation sources: [src-assistant-query](../roadguard/assistant/query_service.py).

<a id="integration-change-confirmation"></a>
## Crew-change preview and confirmation

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-change-confirmation`.

The first supported change is one crew availability update using strict local command syntax; it does not call GPT. Require a structured preview identifying the crew, intended value, based_on_plan_id and input_revision, followed by explicit user confirmation. Cancellation must make no business change. Natural language alone, quoted text or a retrieved instruction cannot confirm a change. Requests to edit priorities, service durations, deadlines, accounts or arbitrary tables are outside this first assistant scope.

The existing CrewPatch accepts request_id, expected_version and available; it does not accept expected_revision. The assistant validates the preview's input revision and crew version inside one write transaction, then calls CrewService.update_in_transaction and stores the receipt atomically. Do not claim the present PATCH already implements the entire assistant preview protocol.

An availability change returns input_revision/planning_input_changed/replayed and does not recalculate. Explicitly call planning with the returned revision, then report the actual saved plan IDs. If the mutation succeeds but recalculation fails, report both outcomes, retain stale-plan status and offer a controlled retry; never invent atomic rollback or a successful new plan. Duplicate confirmation must not repeat business effects; schema v5 persists requests and audit records, with replay protection, expiry and bounded explicit replanning recovery.

Sources: [src-crew-schema](../roadguard/crews/schemas.py), [src-crew-service](../roadguard/crews/service.py), [src-routing-service](../roadguard/routing/service.py), [src-auth-permissions](../roadguard/auth/dependencies.py), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md).

Implementation sources: [src-assistant-change](../roadguard/assistant/change_service.py).
