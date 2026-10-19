# A -> C knowledge package

Package ID: `roadguard-a-knowledge`; version: `a-knowledge-v9`; module owner: A. This is citable project material, without an LLM, embeddings, index, retriever or assistant execution service.

Read [manifest.json](manifest.json) first, then the six English documents listed in documents. Document paths are relative to this directory; sources/context_sources paths are relative to the repository root. Citations use fixed `document_id#section_id` references matching explicit ASCII anchors, independent of automatically generated heading anchors. Include package_version, document_version and relevant scope/rule/label versions to explain older answers.

Each section's classification distinguishes `confirmed_project_fact` (recorded project decisions or current executable behavior), `demo_assumption` (explicitly uncalibrated demonstration parameters/policies), and `pending_decision` (unconfirmed options). A project convention may be settled while its service is still pending; the body makes that distinction. Do not describe planned interface requirements classified as project facts as running features.

v6 synchronized the demo-rules-v2 service-time decision. On 2026-10-18, v7 synchronized source digests for upload-decoding isolation and corrected qa-03's obsolete requirement that all real detections need review: primary raw confidence >=0.60 automatically creates a task, while lower confidence requires review. The six document versions and business rules were unchanged. This maintenance did not implement an assistant or update all B/C knowledge; stage descriptions and runtime-plan provenance still need review before integration. Project-owner confirmation of parameters is not engineering approval; review metadata below only describes package consistency checks.

review_basis is `repository_consistency_review`: a coding agent acting for A checks repository source/configuration consistency. This is neither A's personal signature nor engineering-expert approval, road permission or real experimental validation. The manifest explicitly records `human_or_expert_approval=false`.

sha256 hashes raw UTF-8 file bytes, with LF fixed by .gitattributes. Verify document, source and acceptance-file digests before ingestion. Digest/version mismatches require discontinuing the old material and having A update the package version. Rule changes also require rule-version and table updates. context_sources are explicitly unhashed mutable background documents and cannot replace hashed configuration/code facts. Never copy uploaded images, real inspection databases, credentials or runtime plans into this static package.

[acceptance_cases.json](acceptance_cases.json) supplies ten future-assistant acceptance questions. `supported` means static evidence supports the listed explanation, not that a change was executed. `insufficient_data` means the question requires runtime facts, experiments or road-permission evidence absent from the package; acknowledge the gap and identify missing material. Expected points are acceptance specifications, not fabricated assistant-test results.

Integrity command: `python -m pytest SystemCode/tests/test_knowledge_handoff.py -q`. It checks source digests, citation anchors, label/demo mappings and ten acceptance questions. C must implement retrieval/citations and use B's persisted plan facts for dynamic route answers.

2026-10-18 v8 targeted update synchronized manual-action identity and workflow source hashes with account permissions; older records were not rewritten. See [account roles and CLI](../../../Miscellaneous/ACCOUNT_ROLES.md). Other stage descriptions pending assistant integration retained their existing limitations.

2026-10-19 v9 translates all package prose and acceptance questions into English, updates document versions/digests and the canonical label-display digest, and retains citation anchors and business rules. The label schema retains the legacy `display_name_zh` field key for compatibility; its values now display English. This translation does not validate previously pending services or change historical record semantics.
