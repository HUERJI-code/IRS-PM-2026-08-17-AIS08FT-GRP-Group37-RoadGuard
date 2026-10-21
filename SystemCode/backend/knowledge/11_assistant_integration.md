# RAG integration contract and acceptance requirements

document_id: `rg-kb-integration`; document_version: `7`; owner: `A`.

<a id="integration-status"></a>
## Scope and implementation status

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-status`.

RoadGuard now implements local ChromaDB semantic retrieval with multilingual E5 embeddings, optional GPT evidence selection, saved-plan question context and persistent preview/confirm/cancel/replan endpoints. The assistant is dispatcher-only. Static knowledge passages and embeddings are persisted locally; live plans remain authorized service reads. Real GPT connectivity has been exercised locally; broad semantic acceptance remains outstanding. Provider doubles demonstrate only the local control flow.

C owns retrieval, indexing, citations and answer/change-request services inside the shared backend; A owns knowledge correctness and B owns planning facts. Keep one authoritative task/crew/plan store and reuse the existing domain services. The model must not invent a second scheduler or write business tables directly.

Sources: [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [context-agents](../../../AGENTS.md), [src-routing-service](../roadguard/routing/service.py).

Implementation sources: [src-assistant-api](../roadguard/assistant/api.py).

<a id="integration-ingestion"></a>
## Suggested ingestion and source lifecycle

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-ingestion`.

The local loader validates the knowledge package on every request. A separate setup command embeds token-bounded passages and builds a versioned persistent Chroma collection; requests never download weights or rebuild indexes. Read manifest.json and verify all pinned document/source/guide/acceptance digests before indexing. Index only manifest-listed knowledge sections, using explicit anchors as passage boundaries. Retain title, document_id, section_id, citation_id, document_version, package_version, classification, source_ids and raw-file hash. If a section must be subdivided, retain its parent citation and mark the child position; do not separate a claim from its demo/status limitations.

Treat unchanged labels and business rules as versioned evidence. Changed files invalidate prior digests and require a new reviewed package; never relabel old chunks as current. Build a replacement index before switching active versions and retain enough metadata to audit historical answers. Runtime records retain their frozen rule versions; if matching evidence is absent, request it instead of substituting today's table.

Mutable context_sources explain background and responsibility but do not override hashed executable/configuration facts. Do not bulk-index the whole repository, historical reports, secrets, uploaded images, SQLite files or synthetic runtime fixtures as current operational truth. The interface and generated answers use English; multilingual question matching retains stable source IDs and schema terms. The current baseline uses local multilingual E5 vectors and cosine ranking with explicit limits. Retrieval sends selected passages to the evidence selector; cross-language coverage and answer sufficiency still require evaluation.

Sources: [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [context-agents](../../../AGENTS.md), [src-workflow-schema](../roadguard/schemas/workflow.py), [src-workflow-service](../roadguard/inspections/service.py).

Implementation sources: [src-vector-store](../roadguard/assistant/vector_store.py), [src-embedding](../roadguard/assistant/embedding.py), [src-semantic-retrieval](../roadguard/assistant/retrieval.py), [src-retrieval-setup](../roadguard/assistant/VECTOR_RETRIEVAL.md).

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

c-assistant-query-v3 returns status, supported, answer, selections, sources, package/manifest versions, saved-plan evidence and business_changes_applied=false. For answer_mode=grounded_summary, one provider call selects at most six server-owned evidence IDs and drafts a concise natural-language answer in English; it never authors quote text. The server renders canonical repair-rule answers directly from validated rows. Other answers use the draft after checking numerical literals, priorities and business identifiers against selected evidence. These checks do not establish complete semantic entailment. The frontend displays the answer first and collapses original quotations, versions and provenance by default. The backend restores exact source spans and required context (at most twelve selections), then rejects forged citations, altered or duplicate quotes and incorrect explicitly named damage rows. English/Chinese terminology aliases use longest non-overlapping matches so deep, sunken and wide labels do not collapse into their base classes. Comparisons that omit a named table row return insufficient_data. These bounded guards do not prove general semantic correctness for arbitrary phrasing. A configured provider is not evidence of successful real connectivity. Two-plan comparison is not supported by this query contract.

Standalone assistant identity questions return status=model_info and answer_mode=server_configuration using the backend's configured assistant model name. They do not invoke GPT, retrieval or saved-plan reads, and remain available when generation is disabled or has no key. A missing model name is stated explicitly; configuration is not proof of a completed provider call. Clearly unrelated questions return status=out_of_scope, supported=false and answer_mode=scope_guidance with RoadGuard examples. Both direct paths return model_called=false, empty selections/sources and null package_version, manifest_sha256 and plan. They still require dispatcher authentication, CSRF and valid request fields. Bounded intent matching does not grant action permissions or exempt mixed project questions from RAG validation. Ambiguous questions follow the evidence path; insufficient evidence receives guidance while invalid evidence remains a validation error.

Each factual paragraph must have sufficient evidence. A static citation such as rg-kb-routing#routing-objective supports the formula, not a numeric claim about today's plan. Dynamic statements need the saved plan facts as well. Say insufficient_data when evidence is absent; distinguish that from authorization errors or an explicitly empty saved plan. supported=true describes an evidenced answer, never proof that an action ran.

The acceptance_cases.json file supplies synthetic expected answers and forbidden claims. Execute retrieval/answer tests against the integrated service; record actual citations, supporting passages, access outcomes and refusal/missing-data behavior. Do not mark specifications as passed merely because they parse or their hashes match.

Sources: [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-routing-models](../roadguard/routing/models.py), [src-routing-service](../roadguard/routing/service.py), [src-auth-permissions](../roadguard/auth/dependencies.py).

Implementation sources: [src-assistant-query](../roadguard/assistant/query_service.py), [src-assistant-evidence](../roadguard/assistant/evidence.py), [src-assistant-provider](../roadguard/assistant/provider.py), [src-assistant-query-models](../roadguard/assistant/query_models.py), [src-assistant-answering](../roadguard/assistant/answering.py), [src-assistant-intents](../roadguard/assistant/intents.py).

<a id="integration-change-confirmation"></a>
## Crew-change preview and confirmation

classification: `confirmed_project_fact`. citation_id: `rg-kb-integration#integration-change-confirmation`.

Supported changes are crew availability, task reassignment and task cancellation; they use deterministic domain services without GPT. A task preview identifies action, task_id, target_crew_id when moving, based_on_plan_id and input_revision. It returns before/after route totals and checks travel, service and configured depot-return time against the shift. No other assigned task may be evicted to make a move fit. Infeasible previews are rejected without business changes. Discarding a preview differs from confirming cancellation of a task. Natural language alone, quoted text or retrieved instructions cannot confirm changes. Priority, duration, deadline and account edits remain outside this scope.

The existing CrewPatch accepts request_id, expected_version and available; it does not accept expected_revision. The assistant validates the preview's input revision and crew version inside one write transaction, then calls CrewService.update_in_transaction and stores the receipt atomically. Do not claim the present PATCH already implements the entire assistant preview protocol.

Task confirmation rechecks input/task versions and a fingerprint of routing configuration and depot. A move stores a durable crew constraint; cancellation calls the authoritative workflow service and preserves history. Greedy and GA honor these constraints after new tasks arrive. Unavailable or infeasible locked assignments stay explicitly unassigned. Availability and task changes increment input revision but do not recalculate. Explicitly replan and report the actual saved plan IDs. If planning fails, retain the confirmed change, stale-plan status and a controlled retry receipt. Duplicate confirmation cannot repeat business effects. Schema v6 adds task-change receipts, audit events and persistent crew constraints, preserving existing business records and revision during migration.

Sources: [src-crew-schema](../roadguard/crews/schemas.py), [src-crew-service](../roadguard/crews/service.py), [src-routing-service](../roadguard/routing/service.py), [src-auth-permissions](../roadguard/auth/dependencies.py), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md).

Implementation sources: [src-assistant-change](../roadguard/assistant/change_service.py).

Task sources: [src-task-change-service](../roadguard/assistant/task_change_service.py), [src-task-change-models](../roadguard/assistant/task_change_models.py), [src-task-change-schema](../roadguard/assistant/task_change_schema.py), [src-workflow-service](../roadguard/inspections/service.py).
