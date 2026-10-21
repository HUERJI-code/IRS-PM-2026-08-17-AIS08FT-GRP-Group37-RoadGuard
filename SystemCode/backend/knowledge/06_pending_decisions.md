# Pending choices and further evidence

document_id: `rg-kb-pending`; document_version: `8`; owner: `A`.

<a id="pending-business"></a>
## Business and scenario decisions pending

classification: `pending_decision`. citation_id: `rg-kb-pending#pending-business`.

On 2026-10-14, course-simulation demo-rules-v2 durations were finalized: eight severity/priority mappings remain unchanged, with P3/P2/P1 expected service times 60/120/240 minutes. One primary box >= 0.60 automatically creates one task; lower confidence requires review. These durations are neither deadlines nor measured values. Formal engineering rules and real-scenario calibration still lack evidence. The executable routing demo already specifies a 480-minute shift, return to depot and b-objective-v1 weights. Formal operational approval/calibration of these values, crew capability assumptions and task deadlines remain pending. Vehicle access at the NUS-ISS reference point and task-road eligibility remain unverified. Optional Google matrices and saved Google experiments exist; they do not establish road-work permission or current traffic.

due_at=null means no defined task deadline; the shared project return_to_depot=null means no defined operational return policy, while the routing demo explicitly selects true. Unknown duration is not zero, no available plan is not a valid empty plan, and unreachable travel is not zero minutes.

Sources: [src-project-config](../../config/project.example.json), [src-demo-rules](../../config/demo_rules.example.json), [context-agents](../../../AGENTS.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md), [src-routing-config](../../config/routing.example.json), [src-google-matrix](../roadguard/routing/google_matrix.py), [src-routing-results](../../experiments/routing/results/README.md).

<a id="pending-evaluation"></a>
## Algorithm, model and integration evidence

classification: `pending_decision`. citation_id: `rg-kb-pending#pending-evaluation`.

The main comparison uses four crews and 10/15/20 tasks, with identical inputs, travel matrices and constraints for GA and Greedy. B has delivered encoding, parameters, stopping conditions, objective weights, multi-seed experiments and persisted plans. The new routing/evaluation documents explain their evidence and limits; general superiority or optimality is not established. Report algorithm runtime, external API waiting and travel/service durations separately. More crews do not imply faster algorithm execution.

Full data-content verification, splits and real-model training/held-out metrics must cite actual records of the corresponding Step 8 run. Valid model numbers do not establish business accuracy acceptance; experimental models are not calibrated automatic-acceptance systems. The committed primary-label confirmation metrics are below both 70% targets and reuse validation data; independent local evaluation is still needed. B's persisted plans and the local inspection-to-planning integration exist. C's local ChromaDB retrieval with multilingual E5 embeddings, citations, authorized saved-plan context and preview/confirm/replan flow are implemented. Recorded targeted real GPT checks exercised rule citations, grounded summaries and saved-plan facts. These dated scenarios do not establish broad semantic reliability or acceptance of a later package. Provider doubles verify local control flow only; package integrity tests and synthetic acceptance questions do not measure answer quality. Broader multilingual/paraphrase evaluation and independent clean-machine setup and workflow acceptance remain pending.

Sources: [src-project-config](../../config/project.example.json), [context-agents](../../../AGENTS.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md), [src-routing-service](../roadguard/routing/service.py), [src-ga-evaluation](../../experiments/routing/results/ga-evaluation-v1/summary.json), [src-vision-evaluation](../../experiments/vision/single_damage_summary.json), [src-integration-record](../../../Miscellaneous/INTEGRATION_ACCEPTANCE_20261018.md), [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx).

Implementation sources: [src-assistant-api](../roadguard/assistant/api.py).

Evidence records: [src-rule-citation-acceptance](../../../Miscellaneous/RAG_RULE_CITATION_ACCEPTANCE_20261021.md), [src-intent-live-acceptance](../../experiments/assistant/intent-routing-20261021.json).

Retrieval sources: [src-vector-store](../roadguard/assistant/vector_store.py), [src-embedding](../roadguard/assistant/embedding.py), [src-semantic-retrieval](../roadguard/assistant/retrieval.py).
