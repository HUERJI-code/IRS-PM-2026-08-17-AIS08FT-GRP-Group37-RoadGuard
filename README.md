# RoadGuard

**Status (2026-10-21): the authenticated inspection-to-completion prototype, four-crew planning, dispatcher assistant and final group report are delivered. Local ChromaDB/E5 retrieval is implemented; targeted real GPT and workflow acceptance has passed; broad semantic reliability, presentation videos and clean-machine installation remain outstanding.**

Road damage assessment and maintenance planning for **Jurong, Singapore**, with **four repair crews**.

This repository follows the [IRS-PM project submission template](https://github.com/IRS-PM/Workshop-Project-Submission-Template). The shared FastAPI backend now persists image inspections, reviews and tasks using explicitly selected synthetic detections and versioned demo rules. It validates the frozen Jurong polygons; road eligibility remains user-declared. Step 8 adds opt-in local real inference with primary-confidence-based automatic tasks and review below the threshold; [actual training and acceptance evidence](Miscellaneous/STEP8_VISION_ACCEPTANCE.md) is recorded separately. Four-crew Greedy/GA planning and the React frontend are implemented, including inspector, dispatcher and fixed-crew access. See the [integration record](Miscellaneous/INTEGRATION_ACCEPTANCE_20261018.md) and [frontend guide](SystemCode/frontend/README.md).

> Current geographic baseline: repair tasks are restricted to Jurong East and Jurong West, with four crews departing from the NUS-ISS simulated origin by default. A's Steps 3–7 delivered shared foundations, simulated workflows, consistent task snapshots and B/C handoff materials. Step 8 supports real detection: a primary box ≥0.60 automatically creates a task; lower confidence requires review. Business rules remain course simulations; road declarations and synthetic task points do not replace road verification.

2026-10-14: The [finalized business rules](Miscellaneous/BUSINESS_RULES_BASELINE.md) use `demo-rules-v2`, with P3/P2/P1=60/120/240 minutes. The [integration acceptance checklist](Miscellaneous/INTEGRATION_ACCEPTANCE_CHECKLIST.md) covers A's current checks and scenarios after B/C are ready. The later [18 October acceptance](Miscellaneous/INTEGRATION_ACCEPTANCE_20261018.md) verifies integration with planning and the frontend; existing records retain their frozen rules.

## SECTION 1 : PROJECT TITLE

**RoadGuard: Road Damage Assessment and Four-Crew Maintenance Planning in Jurong**

| Item | Value |
| --- | --- |
| Course | Intelligent Reasoning Systems (IRS) Practice Module |
| Group | Group 7; repository team label: Group7 |
| Demonstration area | Jurong East and Jurong West, Singapore; frozen URA MP2025 boundary |
| Repair crews | Four simulated crews, sharing the NUS-ISS simulated dispatch origin outside the task area |
| Current phase | Real inspection, review, tasks, four-crew planning and crew completion implemented; final report available; query-v3 assistant and persistent task adjustments implemented; targeted real GPT cases passed; broad reliability and videos pending |
| Course start date / batch code | 2026-08-17 / AIS08FT |

Repository name: `IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard`.

Private repository: [HUERJI-code / RoadGuard](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard).

`Group7` represents the confirmed group number; no separate formal team name has been supplied.

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

RoadGuard is a working local web prototype that connects road damage observations to maintenance decisions. An inspector submits a road image and its location. A YOLO detector supplies a damage label, box and confidence; versioned demonstration rules map the label to severity, priority and repair duration. A confidence gate sends uncertain results for human review, while accepted results pass through explicit priority rules and enter the maintenance queue.

The completed [30-epoch YOLO11n/YOLO11s comparison](Miscellaneous/VISION_30_EPOCH_COMPARISON.md) selects YOLO11s by validation mAP50-95. It improves recall at the fixed confidence threshold while increasing false positives and CPU latency; the current user-selected workflow accepts the primary detection at confidence >= 0.60; lower confidence requires review. This setting does not improve model accuracy. See [one-box responses and fields](Miscellaneous/INSPECTION_RESPONSE_FIELDS.md).

The subsequent [balanced Precision/Recall experiment](Miscellaneous/BALANCED_VISION_OPTIMIZATION.md) completed another 40 fine-tuning epochs and compared four validation candidates. The selected checkpoint reaches 50.5% Precision and 52.0% Recall at confidence 0.25 with correct eight-class, IoU 0.5 matching, versus 48.6% / 51.2% for the parent. The requested simultaneous 70% target remains unmet, and some damage types regressed. The deployed single-v1 model uses those balanced weights, original-only 832-pixel inference and area-quarter primary selection at inference confidence 0.20. Eight-class primary image-type Precision/Recall are 61.63%/61.99% on reused validation confirmation data, not an independent local test. See the [model release](Miscellaneous/MODEL_RELEASE_AND_BACKEND.md) and [single-damage evaluation](Miscellaneous/SINGLE_DAMAGE_OPTIMIZATION.md).

A group-built genetic algorithm (GA) assigns accepted tasks to four crews and determines visit order. Greedy uses the same task snapshot, travel matrix and evaluator. Changes mark saved plans stale; dispatchers explicitly recalculate. Evaluation compares priority-first coverage, a weighted scheduling objective, travel, workload and runtime. No task deadlines are supplied, so priority-weighted completion is not lateness. See the [routing experiments](SystemCode/experiments/routing/README.md).

Repair tasks are limited to Jurong East and Jurong West. The maintenance department and tasks are simulated, with the real NUS-ISS location used as a shared simulated dispatch origin outside the task area; these are not official maintenance records or an actual NUS-ISS maintenance operation. Origin-to-task travel must be counted. RDD2022ES version 1 is the implemented eight-class image dataset. The dispatcher assistant uses reviewed project knowledge and authorized saved-route facts, with local vector retrieval and optional GPT evidence selection.

The assistant returns English answers first, with sources closed until requested. Query-v3 distinguishes grounded summaries from direct model-configuration information and scope guidance; direct responses do not call GPT. Dispatcher task moves and cancellation require preview and explicit confirmation, with travel/service/return feasibility checks and durable crew constraints. Recalculation remains explicit. See the [task-adjustment acceptance](Miscellaneous/TASK_ADJUSTMENT_ACCEPTANCE_20261021.md) and [intent-routing acceptance](Miscellaneous/RAG_INTENT_ROUTING_ACCEPTANCE_20261021.md); targeted cases do not establish broad answer accuracy.

Measured vision results must be read with the corresponding experimental run and limitations. The project does not claim measured cost savings or operational readiness.

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official full name | Student ID | Work items / contribution | Email (optional) |
| --- | --- | --- | --- |
| Hu Erji | A0305480L | Vision/data experiments, business rules, shared backend, integration, authentication and later interface refinement | |
| Yan GuanTing | A0305485B | Four-crew Greedy/GA planning, crew and plan persistence, Google matrix provider and routing experiments | |
| Wu TaoYi | A0356972M | Frontend foundation and workflow pages, map/comparison integration and the retrieval/confirmed-change assistant | |

The contribution table and final report include the later assistant delivery. Prepare the submission roster using [member-github.example.txt](Miscellaneous/member-github.example.txt).

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

Two separate videos are required by the current course briefing:

| Video | Target duration | Content | Status |
| --- | --- | --- | --- |
| Promotion / use-case demonstration | 5 minutes | Business pain, value and working use cases | Planned |
| System design / technical explanation | 5 minutes | Architecture, reasoning methods and technical walkthrough | Planned |

See [Video/README.md](Video/README.md) for naming and recording requirements.

## SECTION 5 : USER GUIDE

Follow the [installation and user guide](ProjectReport/INSTALLATION_AND_USER_GUIDE.md) for Python 3.12, Node 22, account provisioning and both startup commands. Open the React app at `http://127.0.0.1:5173`; API documentation is at `http://127.0.0.1:8000/docs`. The [backend guide](SystemCode/backend/README.md), [frontend guide](SystemCode/frontend/README.md) and [account roles](Miscellaneous/ACCOUNT_ROLES.md) describe the available workflows. Before using the assistant, follow the [ChromaDB and embedding setup](SystemCode/backend/roadguard/assistant/VECTOR_RETRIEVAL.md); real GPT questions also require the existing server-side provider configuration. Use the [API contract](Miscellaneous/API_CONTRACT.md) for current interfaces; fixed examples are synthetic inputs, not automatically loaded application data.

Repository layout:

```text
IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard/
  README.md
  AGENTS.md
  SystemCode/
    config/project.example.json
    backend/
    frontend/
    model/
    experiments/
    tests/
  ProjectReport/
    REPORT_OUTLINE.md
    INSTALLATION_AND_USER_GUIDE.md
    COURSE_MAPPING.md
    Proposal/
    figures/
  Video/
  Miscellaneous/
    PROJECT_SCOPE.md
    JURONG_SCOPE_AND_DEPOT.md
    geography/
    IMPLEMENTATION_PLAN.md
    SUBMISSION_CHECKLIST.md
    TEMPLATE_SOURCE.md
    member-github.example.txt
```

Start by reviewing the [project scope](Miscellaneous/PROJECT_SCOPE.md), [example configuration](SystemCode/config/project.example.json) and [implementation plan](Miscellaneous/IMPLEMENTATION_PLAN.md).

All contributors and coding agents should first read the shared [project and agent collaboration rules](AGENTS.md). The file includes module boundaries, interface-change rules, validation requirements and a reusable agent kickoff prompt.

## SECTION 6 : PROJECT REPORT / PAPER

The [current final group report](ProjectReport/IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard-Group-Report.docx) is available in `ProjectReport/`. It includes the complete submitted proposal, the MR/RS/CGS mapping, and installation/user instructions. See the [report guide](ProjectReport/README.md) for scope and remaining limitations.

Required appendices include the proposal, functionality-to-course mapping, and installation/user guide. Individual reflections and peer evaluations are submitted confidentially through the individual Canvas assignment, following the current briefing.

## SECTION 7 : MISCELLANEOUS

- [Project and agent collaboration rules](AGENTS.md)
- [Feature branches, pull requests and CI](Miscellaneous/GITHUB_WORKFLOW.md)
- [Confirmed scope and open design decisions](Miscellaneous/PROJECT_SCOPE.md)
- [Jurong boundary and NUS-ISS simulated dispatch origin](Miscellaneous/JURONG_SCOPE_AND_DEPOT.md)
- [RDD2022ES version and eight-class label audit](Miscellaneous/DATASET_AND_LABEL_AUDIT.md)
- [Validation error analysis and 30-epoch model comparison](Miscellaneous/VISION_30_EPOCH_COMPARISON.md)
- [Balanced Precision/Recall optimization and unmet 70% target](Miscellaneous/BALANCED_VISION_OPTIMIZATION.md)
- [Frozen initial API contracts and demo examples](Miscellaneous/API_CONTRACT.md)
- [Run demo detection and business rules](Miscellaneous/DEMO_DETECTION_AND_RULES.md)
- [Upload, review and manage persisted tasks](Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md)
- [B/C task snapshots, fixed inputs and knowledge handoff](Miscellaneous/BC_HANDOFF.md)
- [RAG knowledge corpus: GA, plans, operations, evidence and integration requirements](SystemCode/backend/knowledge/README.md)
- [Implementation milestones](Miscellaneous/IMPLEMENTATION_PLAN.md)
- [Three-person work allocation and interface draft](Miscellaneous/TEAM_WORK_ALLOCATION.md)
- [Submission checklist and file naming](Miscellaneous/SUBMISSION_CHECKLIST.md)
- [Template and requirement provenance](Miscellaneous/TEMPLATE_SOURCE.md)
- [Member / GitHub submission file template](Miscellaneous/member-github.example.txt)

Development started from this course scaffold. The previous prototype has been abandoned at the project owner's request; its code and historical results are not part of this project baseline.
