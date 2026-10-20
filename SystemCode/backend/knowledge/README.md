# A -> C knowledge package

Package ID: `roadguard-a-knowledge`; version: `a-knowledge-v10`; reviewed: 2026-10-20; content owner: A; retrieval/integration owner: C. This is a static RAG handoff, not an implemented LLM, embedding pipeline, index, retriever or assistant execution service.

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
| [11 RAG integration](11_assistant_integration.md) | Ingestion, authorized runtime facts, citations and future confirmation |

v10 corrects outdated claims that planning/crew APIs and experiments are still undelivered. The algorithms, saved-plan services and authenticated workspaces exist; GPT/RAG answers and assistant preview/confirm/cancel flows remain pending. It distinguishes the project's undecided operational return policy from the implemented return-to-depot/480-minute routing demo. Labels and demo-rule values are unchanged.

## Evidence and citation contract

Document paths are relative to this directory; source paths are relative to the repository root. Citations use stable `document_id#section_id` IDs with explicit ASCII anchors. Preserve package_version, document_version, source_ids, hashes and relevant scope/rule/label/routing versions. Static citations support explanations; live route claims also require the authorized saved plan/revision/fields. Current defaults never overwrite frozen historical task rules.

Classifications are `confirmed_project_fact`, `demo_assumption` and `pending_decision`. A confirmed project requirement may specify future behavior; read the implementation-status wording before claiming it exists. Routing configuration values are demonstration assumptions, not approved engineering policy.

review_basis is `repository_consistency_review`, performed by a coding agent on behalf of A; `human_or_expert_approval=false`. This is neither a personal signature nor expert approval, road permission, field validation or executed assistant evaluation.

## Ingestion and maintenance

Verify raw-byte SHA-256 digests for documents, pinned sources, this guide and acceptance cases before ingestion. Knowledge files use UTF-8/LF with a final newline. A mismatch stops ingestion until the changed source and affected passages are reviewed and the package version/digests updated. Source `version` identifies the configuration or reviewed repository snapshot; hashes identify exact bytes. Mutable context_sources are explicitly unhashed background and cannot override pinned code/configuration.

Index only manifest-listed sections and retain their claim/status/limitation context. Do not indiscriminately index repository history, credentials, databases, uploads or synthetic task fixtures. Do not embed live operational records into this shared static corpus. The [integration contract](11_assistant_integration.md) describes proposed chunk metadata, lifecycle, access controls and answer/action boundaries. The backend APIs remain the source of authorized live facts.

[acceptance_cases.json](acceptance_cases.json) contains 30 synthetic future-assistant cases. `supported` means available evidence supports the explanation, not that an action ran. `insufficient_data` identifies missing live/version/permission evidence. Expected answers and forbidden claims are specifications, not recorded RAG outcomes.

Run `python -m pytest SystemCode/tests/test_knowledge_handoff.py -q` from the repository root to check hashes, sources, anchors, label/rule mappings and acceptance specifications. These checks do not run GPT or demonstrate retrieval quality. Implement and test the retrieval/answer/confirmation service separately before reporting RAG as complete.

## Earlier revisions

v6 synchronized demo-rules-v2; v7 corrected the real primary-confidence acceptance case and image-decoding hash; v8 aligned authenticated manual-action provenance; v9 translated the six original documents into English. These historical revisions remain history, not the current ingestion target. v10 extends the corpus to eleven documents and refreshes current B/C status while retaining stable existing citation anchors.
