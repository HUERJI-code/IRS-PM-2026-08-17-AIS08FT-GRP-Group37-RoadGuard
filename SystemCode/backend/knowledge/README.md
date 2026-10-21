# A -> C knowledge package

Package ID: `roadguard-a-knowledge`; version: `a-knowledge-v18`; reviewed: 2026-10-21; content owner: A; retrieval/integration owner: C. This directory contains static evidence. The assistant implements local ChromaDB/E5 retrieval, opt-in grounded answers and confirmed crew/task changes. Targeted real GPT cases are recorded; broader semantic evaluation and independent clean-machine acceptance remain pending. Historical result files retain their original package versions and are not new v18 test results.

## Corpus map

Read [manifest.json](manifest.json), then its eleven English documents:

| Document | Questions it supports |
| --- | --- |
| [01 Scope](01_scope.md) | Jurong boundary, depot, four crews and road evidence |
| [02 Labels](02_labels.md) | Eight canonical damage labels and visual limitations |
| [03 Demo rules](03_demo_rules.md) | Priority, service duration and demo selection policy |
| [04 Workflow](04_workflow.md) | Real/demo detection, review, task states and versions |
| [05 Answer boundaries](05_assistant_boundaries.md) | Static versus dynamic evidence and unsupported claims |
| [06 Pending work](06_pending_decisions.md) | Operational validation and unfinished assistant work |
| [07 Routing algorithms](07_routing_algorithms.md) | Greedy, GA encoding/operators, constraints, objective and demo settings |
| [08 Saved plans](08_route_plans_and_comparisons.md) | Provenance, stale plans, unassigned reasons and fair comparisons |
| [09 Accounts and operations](09_accounts_and_operations.md) | Permissions, workflow, installation and troubleshooting |
| [10 Evaluation evidence](10_evaluation_evidence.md) | Historical routing/model results and their limits |
| [11 RAG integration](11_assistant_integration.md) | Ingestion, authorized runtime facts, citations and explicit confirmation |

Historical v10 corrected claims that planning/crew APIs and experiments were undelivered. At that revision, GPT/RAG answers and assistant preview/confirm/cancel flows were still pending; later revisions below implement them. It distinguished the project's undecided operational return policy from the implemented return-to-depot/480-minute routing demo. Labels and demo-rule values are unchanged.

## Evidence and citation contract

Document paths are relative to this directory; source paths are relative to the repository root. Citations use stable `document_id#section_id` IDs with explicit ASCII anchors. Preserve package_version, document_version, source_ids, hashes and relevant scope/rule/label/routing versions. Static citations support explanations; live route claims also require the authorized saved plan/revision/fields. Current defaults never overwrite frozen historical task rules.

Classifications are `confirmed_project_fact`, `demo_assumption` and `pending_decision`. A confirmed project requirement may specify future behavior; read the implementation-status wording before claiming it exists. Routing configuration values are demonstration assumptions, not approved engineering policy.

review_basis is `repository_consistency_review`, performed by a coding agent on behalf of A; `human_or_expert_approval=false`. This is neither a personal signature nor expert approval, road permission, field validation or executed assistant evaluation.

## Ingestion and maintenance

Verify raw-byte SHA-256 digests for documents, pinned sources, this guide and acceptance cases before ingestion. Knowledge files use UTF-8/LF with a final newline. A mismatch stops ingestion until the changed source and affected passages are reviewed and the package version/digests updated. Source `version` identifies the configuration or reviewed repository snapshot; hashes identify exact bytes. Mutable context_sources are explicitly unhashed background and cannot override pinned code/configuration.

Index only manifest-listed sections and retain their claim/status/limitation context. Do not indiscriminately index repository history, credentials, databases, uploads or synthetic task fixtures. Do not embed live operational records into this shared static corpus. The [integration contract](11_assistant_integration.md) describes implemented chunk metadata, lifecycle, access controls and answer/action boundaries. The backend APIs remain the source of authorized live facts.

[acceptance_cases.json](acceptance_cases.json) contains 30 synthetic assistant acceptance specifications. `supported` means available evidence supports the explanation, not that an action ran. `insufficient_data` identifies missing live/version/permission evidence. Expected answers and forbidden claims are specifications, not recorded RAG outcomes.

Run `python -m pytest SystemCode/tests/test_knowledge_handoff.py -q` from the repository root to check hashes, sources, anchors, label/rule mappings and acceptance specifications. These checks do not run GPT or demonstrate retrieval quality. The implemented retrieval/answer/confirmation service has separate local tests and targeted live records; broader semantic and clean-machine acceptance remain pending.

## Earlier revisions

v6 synchronized demo-rules-v2; v7 corrected the real primary-confidence acceptance case and image-decoding hash; v8 aligned authenticated manual-action provenance; v9 translated the six original documents into English. These historical revisions remain history, not the current ingestion target. v10 extends the corpus to eleven documents and refreshes current B/C status while retaining stable existing citation anchors.

v11 reconciles C's feature with the eleven-document English corpus, preserves its two additional citation anchors and refreshes affected source hashes. Its 40 sections include routing, account roles and the current assistant boundaries. No historical experiment record is rewritten.

## Chroma and embeddings introduced in v12

v12 uses persistent ChromaDB and pinned local multilingual E5 embeddings. See the [vector retrieval guide](../roadguard/assistant/VECTOR_RETRIEVAL.md) for setup, reindexing and current contracts. The forty stable parent sections are split into token-bounded passages; live plans and account data remain outside the vector database. Rebuild the index after a reviewed manifest/source change.

## Rule evidence selection introduced in v13

v13 retains the same eight labels, rule values, eleven documents and forty parent
citations. GPT selects server-owned evidence IDs; the backend restores exact
source spans. Specific label questions expose only matching rows from the rule
and label tables, using bounded English/Chinese aliases. Table headings and
demo/version qualifications accompany each row as separate verbatim selections;
nonadjacent text is never represented as one quote. Existing source, substring,
duplicate, rule-version and saved-plan revision checks remain mandatory.
See the [assistant guide](../roadguard/assistant/README.md) for limitations and tests.
Rebuild the local Chroma index after this manifest update; model weights are reused.

## Historical answer-first summaries in v14

Version 14 introduced c-assistant-query-v2 with answer_mode=grounded_summary; v16 subsequently introduced the current query-v3 contract.
The answer is readable prose; selections and sources retain the exact evidence.
One GPT request selects evidence IDs and drafts a short answer. Canonical repair
table answers are rendered from validated rows; other summaries use the draft
with bounded checks on numbers, priorities and business identifiers. These checks
do not prove full semantic entailment. The frontend shows the answer first and
keeps original quotations, provenance and versions in a closed sources disclosure.
Update the frontend OpenAPI snapshot/types with the backend. Rebuild the local
index with cached embeddings; no business-data migration or model change is needed.

## Persistent task adjustments and English output introduced in v15

The dispatcher loads a saved plan, reviews all crew routes, and previews an assigned
active task move or active task cancellation. Server feasibility includes travel,
service and configured depot return. Confirmation persists crew affinity or task
cancellation; subsequent explicit Greedy/GA runs honor the saved affinity even
when new tasks arrive. Unavailable/infeasible locked assignments remain explicitly
unassigned. Preview discard makes no business change. Schema v6 preserves existing
records while adding audited task-change receipts and constraints.

All current UI copy and generated answers use English. Multilingual aliases still
accept non-English questions. Historical experiment strings remain byte-equivalent
JSON values through escaped serialization, with display adaptations and hashes
recorded separately; they are not new test results. This package retains eleven
documents and forty stable parent citations. Rebuild the local index from cached
embeddings after this reviewed update.


## Assistant intent routing introduced in v16

The query-v3 contract separates configured-model information and friendly scope
guidance from grounded project answers. Direct responses have no model/retrieval
call or invented citation. Repair and saved-route questions retain all source,
label, rule-version and plan-revision checks. English answers support bounded
multilingual intent matching. Rebuild the local index after this source update;
the cached embedding model is reused. No business migration or rule change occurs.

## Earlier consistency review in v17

v17 reconciles current scope, pending-work and evaluation passages with the
implemented ChromaDB/E5 service and recorded targeted real GPT checks. It updates
reviewed account, installation and retrieval-setup provenance while retaining
eleven documents, forty parent citations, eight labels and demo-rules-v2 values.
Historical results remain unchanged. Rebuild the local versioned index from cached
embeddings after this update; no new GPT call, embedding download or business-data
migration is implied by this documentation review.

## Administrative Group37 revision in v18

v18 records the owner-confirmed Group37 repository and directory rename on
2026-10-21 and refreshes the pinned deployment-manifest source hash and current package
version examples in the installation and retrieval setup guides. Model weights,
inference settings, experimental results and historical acceptance observations
are unchanged. Acceptance cases remain specifications, not new test observations.
Rebuild the local versioned Chroma index after the directory rename using cached
embeddings; this revision does not execute GPT or download models.
