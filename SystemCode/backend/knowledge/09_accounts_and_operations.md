# Accounts, workflow and local operation

document_id: `rg-kb-operations`; document_version: `3`; owner: `A`.

<a id="operations-roles"></a>
## Role and resource access

classification: `confirmed_project_fact`. citation_id: `rg-kb-operations#operations-roles`.

| Account role | Allowed workspace/actions |
| --- | --- |
| inspector | Upload one photo and read its own inspection results/photos. No global task lists, review or dispatch. |
| dispatcher | Review inspections, manage tasks and crew availability, recalculate/query full plans and compare algorithms. No photo uploads or crew workspace. |
| crew | Read its server-bound crew's latest GA route/tasks/photos and complete its assigned tasks. No crew switching, global plans, cancellation, label/location changes or recalculation. |

The server, not a URL query or model instruction, determines permissions. Inspectors cannot read another uploader's inspections; crews receive only accessible task evidence. Authenticated identity is not engineering accreditation. The dispatcher assistant provides local retrieval, opt-in evidence answers and persistent crew-change preview/confirmation/recovery. Inspector and crew accounts cannot access those assistant endpoints.

The assistant must preserve these server permissions before reading facts and before passing them to an LLM. Static project documents do not authorize access to another account's images, assignments or records. Do not fetch a global plan under elevated credentials and rely on generated text to hide its restricted parts.

Sources: [src-auth-permissions](../roadguard/auth/dependencies.py), [src-auth-access](../roadguard/auth/access.py), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md), [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx).

Implementation sources: [src-assistant-api](../roadguard/assistant/api.py).

<a id="operations-workflow"></a>
## Current user workflow

classification: `confirmed_project_fact`. citation_id: `rg-kb-operations#operations-workflow`.

An inspector uploads a photo with separately supplied in-scope coordinates and a public-road declaration. No detection creates no task. A selected real primary box at raw confidence >=0.60 automatically creates one task; a lower-confidence result awaits dispatcher review. Review is available only while pending_review. Demo-mode selection has its own all-detections gate; do not apply that gate to real primary selection.

Accepted task creation automatically attempts GA and Greedy after the task commits, including confirm/correct approval of a pending inspection. The dispatcher checks the latest saved routes, current input revision and unassigned reasons. If automatic planning fails, the task remains saved and the interface warns that the dispatcher can retry in Four-crew routes. A completed calculation may still contain unassigned tasks due to constraints. Crew members see their fixed crew's latest GA route and can complete assigned active tasks. Corrections, cancellation, completion and availability changes can make saved plans stale; another explicit recalculation updates planning. The interface's schematic map is not turn-by-turn navigation.

Sources: [src-workflow-service](../roadguard/inspections/service.py), [src-routing-service](../roadguard/routing/service.py), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md), [src-install-guide](../../docs/INSTALLATION_AND_USER_GUIDE.md).

Automatic planning sources: [src-automatic-planning](../roadguard/routing/automatic.py), [src-workflow-api](../roadguard/api/workflow.py).

<a id="operations-install"></a>
## Installation and local readiness

classification: `confirmed_project_fact`. citation_id: `rg-kb-operations#operations-install`.

Use Python 3.12 for the full vision application and Node 22.x >=22.12 with npm >=10. Base CI's Python 3.11 environment omits optional vision dependencies; its success is not full-vision compatibility evidence. Follow the linked installation guide from the repository root: create a Python 3.12 virtual environment, install requirements-ci.txt and requirements-vision.txt, provision accounts using roadguard.auth.manage, start uvicorn with --app-dir SystemCode/backend, then run npm ci and npm run dev in SystemCode/frontend.

The deployment weight is bundled and checked against the backend manifest; inference does not need the raw Dataset directory. Account creation is local to the actual runtime database, with hidden password prompts, no default password and no startup-created account. Use the same database configuration for provisioning and the server. Do not put passwords, tokens or API keys in knowledge files.

The public `/api/v1/health` checks application/database access. The real model loads lazily; healthy status does not prove model readiness, Google access or an available GPT/RAG service. Recorded local installation is not independent clean-machine validation.

Sources: [src-install-guide](../../docs/INSTALLATION_AND_USER_GUIDE.md), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md), [src-model-manifest](../../model/releases/roadguard-single-v1.json).

<a id="operations-errors"></a>
## Common operational failures

classification: `confirmed_project_fact`. citation_id: `rg-kb-operations#operations-errors`.

| Symptom | Evidence-based response |
| --- | --- |
| NumPy installation rejects the Python version | Check the environment actually uses Python 3.12 and the full vision requirements. |
| 401 | Sign in again or verify session/account state. |
| 403 | Check the account's role, session-bound X-CSRF-Token for writes, and allowed origin. |
| 404 | The record may be absent or inaccessible; do not infer another user's data exists. A missing route plan may require first recalculation. |
| 409 stale version/revision | Reread the authorized resource/input, review the change and submit a new current request; do not blindly replay changed parameters. |
| Real inference unavailable | Check optional vision installation and bundled weight/manifest; restart after correcting a failed lazy load. |
| 503 travel_matrix_unavailable on manual recalculation | Google matrix acquisition failed; no new plan was saved. Do not present an older or simulated plan as this successful run. |
| X-RoadGuard-Replanning: failed on a successful upload/review | The task was saved, but automatic planning failed. Check saved plans and retry from Four-crew routes; a safe accepted-request replay can also recover missing/stale plans. No simulated fallback is used. |

Browser and script clients retain session cookies; writes require X-CSRF-Token. Use one hostname consistently, since localhost and 127.0.0.1 do not share cookies. Read-only GET calls do not require CSRF. Never use a real password/token as a retrieval example or copy it into an error explanation.

Sources: [src-install-guide](../../docs/INSTALLATION_AND_USER_GUIDE.md), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md), [src-routing-service](../roadguard/routing/service.py).

Automatic planning sources: [src-automatic-planning](../roadguard/routing/automatic.py), [src-workflow-api](../roadguard/api/workflow.py).
