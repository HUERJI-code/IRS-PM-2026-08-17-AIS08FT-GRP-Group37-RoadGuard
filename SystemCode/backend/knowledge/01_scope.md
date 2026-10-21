# Scope, depot and four-crew scenario

document_id: `rg-kb-scope`; document_version: `6`; owner: `A`.

<a id="scope-baseline"></a>
## Project task scope

classification: `confirmed_project_fact`. citation_id: `rg-kb-scope#scope-baseline`.

The repair-task area is the union of frozen URA MP2025 polygons for Jurong East and Jurong West, Singapore, version `jurong-je-jw-mp2025-v1`. Coverage uses the full polygons, including outer and hole boundaries but excluding hole interiors; a bounding rectangle cannot establish task validity. Coordinates use WGS84 decimal degrees; GeoJSON order is longitude, latitude. Photos and positions are submitted separately and do not prove that a photo was captured in Jurong.

Sources: [src-project-config](../../config/project.example.json), [src-boundary](../../../Miscellaneous/geography/jurong-boundary-mp2025.geojson), [src-geography-code](../roadguard/geography.py), [context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md).

<a id="depot-crews"></a>
## Simulated department, depot and crews

classification: `confirmed_project_fact`. citation_id: `rg-kb-scope#depot-crews`.

One fictional repair department uses four simulated crews: `crew-01`, `crew-02`, `crew-03`, `crew-04`. Their shared origin is NUS-ISS, 25 Heng Mui Keng Terrace, latitude `1.292149`, longitude `103.776551`, depot version `nus-iss-v1`. This is a simulated origin at a real address, not actual NUS-ISS repair operations.

This specified depot may lie outside the task area. Travel from depot to first task must be counted, and routes may leave JE/JW. The exception applies only to the depot; a repair task submitted at NUS-ISS coordinates is still rejected. The building reference point has not been verified as a vehicle entrance. The shared project return-to-depot policy remains null/pending confirmation and must not default to no return. The implemented routing demo independently selects return_to_depot=true and a 480-minute shift in b-routing-demo-v1; these are demo assumptions pending operational confirmation. Crew availability, Greedy/GA planning and plan persistence are implemented. Local ChromaDB retrieval with multilingual E5 embeddings, opt-in evidence answers and confirmed crew/task changes are implemented. Recorded targeted real GPT checks exercised rule citations and saved-plan answers; broader semantic reliability and independent clean-machine acceptance remain pending.

Sources: [src-project-config](../../config/project.example.json), [src-depot](../../../Miscellaneous/geography/nus-iss-depot.geojson), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md), [src-routing-config](../../config/routing.example.json), [src-routing-service](../roadguard/routing/service.py), [src-crew-service](../roadguard/crews/service.py), [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx).

Implementation sources: [src-assistant-api](../roadguard/assistant/api.py).

Evidence records: [src-rule-citation-acceptance](../../../Miscellaneous/RAG_RULE_CITATION_ACCEPTANCE_20261021.md), [src-intent-live-acceptance](../../experiments/assistant/intent-routing-20261021.json).

Retrieval sources: [src-vector-store](../roadguard/assistant/vector_store.py), [src-embedding](../roadguard/assistant/embedding.py), [src-semantic-retrieval](../roadguard/assistant/retrieval.py).

<a id="road-evidence"></a>
## Evidence limits of road declarations

classification: `confirmed_project_fact`. citation_id: `rg-kb-scope#road-evidence`.

The project accepts only public motor-road tasks meeting its exclusions: expressway main carriageways/ramps and private or restricted internal roads are excluded. Requests must declare `road_type="public_motor_road"`, with `road_type_source="user_declared"` recorded; other declarations are rejected.

This is caller declaration and geographic validation, not road-network verification, road-permission verification or automatic verification of current access. Passing upload/polygon checks alone cannot establish permission for real repairs or vehicle access. Further evidence from A/B is required; the depot exception cannot imply an exception for task points.

Sources: [src-project-config](../../config/project.example.json), [src-geography-code](../roadguard/geography.py), [src-workflow-schema](../roadguard/schemas/workflow.py), [context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md).
