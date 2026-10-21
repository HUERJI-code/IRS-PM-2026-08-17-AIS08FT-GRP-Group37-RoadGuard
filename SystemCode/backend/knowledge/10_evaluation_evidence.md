# Recorded evaluation evidence and its limits

document_id: `rg-kb-evaluation`; document_version: `3`; owner: `A`.

<a id="evaluation-routing"></a>
## Historical GA evaluation

classification: `confirmed_project_fact`. citation_id: `rg-kb-evaluation#evaluation-routing`.

The committed ga-evaluation-v1 experiment dated 2026-10-15 compares four crews across 12 scenarios: simulated/Google matrix x 480-minute/unlimited shift x 10/15/20 synthetic tasks. Each scenario has Greedy once, pure GA seeds 1-10, Greedy-seeded GA seeds 1-10, and 20 longer reference runs (seeds 101-120): 492 runs total. Reference runs use population 150, maximum 1000 generations and patience 300. Saved matrices were reused; this evaluation did not make new Google calls.

Best-known solution (BKS) means the best of those 41 runs for each scenario, ordered by the priority-first objective; it is not a proven global optimum. All 120 seeded-GA runs beat Greedy in this recorded experiment without fewer assignments. Across scenarios, mean objective reduction is approximately 0.7%-3.6%, mean BKS gap 0.23%-1.82% for seeded GA versus 1.17%-5.10% for Greedy. These percentages concern the stated objective, not travel alone or monetary savings.

Pure GA is not always better: in Google/480/15 it leaves one extra P3 unassigned in 5 of 10 seeds. Its reduced-coverage runs must not be mixed into ordinary cost-gap percentages. Recorded mean runtimes are roughly 105-362 ms for online-style seeded GA and under 1 ms for Greedy on that experiment machine, excluding external matrix acquisition. Different workloads and machines can differ.

These are historical synthetic-task comparisons under saved matrices and demonstration assumptions. They do not describe today's saved plan, validate road access, guarantee all future GA wins, or establish an exact optimality gap. Source run metadata identifies its code/configuration/environment; reproduce that version for experimental comparison.

Sources: [src-routing-results](../../experiments/routing/results/README.md), [src-ga-evaluation](../../experiments/routing/results/ga-evaluation-v1/summary.json), [src-ga-run-metadata](../../experiments/routing/results/ga-evaluation-v1/run_metadata.json).

<a id="evaluation-vision"></a>
## Primary-label metrics and confidence are different

classification: `confirmed_project_fact`. citation_id: `rg-kb-evaluation#evaluation-vision`.

The deployed experimental model is yolo11s-rdd2022es-balanced40-best-single-v1. Its manifest records 832-pixel inference, minimum detection confidence 0.20 and area_quarter primary ranking. That inference threshold differs from the workflow's 0.60 raw-confidence gate for automatic task creation.

The committed single_damage_summary.json records 377 confirmation images (171 positive, 206 negative), with TP=106, FP=66, FN=65. Image-type precision is 61.63%, recall 61.99%, and eight-class macro F1 46.15%. These are primary-label image-type measures; they are not box-IoU localization or mAP metrics. The source separately records localization thresholds and multi-object evaluation.

This confirmation subset came from validation data already used for training/selection; it is not an independent held-out Jurong field test. Both typed precision and recall remain below the project's 70% targets. A confidence of 0.60 is not a measured 60% correctness probability, and passing software tests does not establish recognition accuracy or calibration. Source data does not prove Singapore/Jurong image provenance.

Sources: [src-model-manifest](../../model/releases/roadguard-single-v1.json), [src-vision-evaluation](../../experiments/vision/single_damage_summary.json), [src-workflow-service](../roadguard/inspections/service.py).

<a id="evaluation-readiness"></a>
## Software acceptance versus assistant evaluation

classification: `confirmed_project_fact`. citation_id: `rg-kb-evaluation#evaluation-readiness`.

The dated integration record documents the implemented local inspection-to-planning workflow. Account/workspace access is described in the account guide. Cite the date and exact tested scenario when using those records; a historical acceptance record does not demonstrate every later environment or feature.

The assistant UI and local retrieval/change workflows are implemented. Static hashes establish source consistency, not retrieval relevance, sufficient answers or expert approval. Local tests use explicit provider doubles and exercise citation rejection, roles, stale evidence and confirmed-change recovery. Targeted local real GPT checks on 2026-10-21 exercised rule citations, answer-first summaries, saved-plan facts and intent routing; direct model/scope responses made no provider call. Their records retain the package and contract tested at the time. They do not certify this later package or establish broad semantic answer quality. Local ChromaDB/E5 retrieval is implemented; broader multilingual relevance and sufficiency evaluation and independent clean-machine acceptance remain pending. This package supplies synthetic acceptance specifications, not general real-model answer scores.

Sources: [src-integration-record](../../../Miscellaneous/INTEGRATION_ACCEPTANCE_20261018.md), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md), [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx).

Implementation sources: [src-assistant-api](../roadguard/assistant/api.py).

Evidence records: [src-rule-citation-acceptance](../../../Miscellaneous/RAG_RULE_CITATION_ACCEPTANCE_20261021.md), [src-intent-live-acceptance](../../experiments/assistant/intent-routing-20261021.json).

Retrieval sources: [src-vector-store](../roadguard/assistant/vector_store.py), [src-embedding](../roadguard/assistant/embedding.py), [src-semantic-retrieval](../roadguard/assistant/retrieval.py).
