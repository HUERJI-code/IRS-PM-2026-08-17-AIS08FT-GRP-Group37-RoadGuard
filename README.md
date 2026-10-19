# RoadGuard

**Status: persisted workflows, B/C handoff and Step 8 real-vision tooling delivered; experimental training evidence is tracked separately.**

Road damage assessment and maintenance planning for **Jurong, Singapore**, with **four repair crews**.

This repository follows the [IRS-PM project submission template](https://github.com/IRS-PM/Workshop-Project-Submission-Template). The shared FastAPI backend now persists image inspections, reviews and tasks using explicitly selected synthetic detections and versioned demo rules. It validates the frozen Jurong polygons; road eligibility remains user-declared. Step 8 adds opt-in local real inference with primary-confidence-based automatic tasks and review below the threshold; [actual training and acceptance evidence](Miscellaneous/STEP8_VISION_ACCEPTANCE.md) is recorded separately. Routing and frontend remain pending.

> Current geographic baseline: repair tasks are restricted to Jurong East and Jurong West, with four crews departing from the NUS-ISS simulated origin by default. A's Steps 3–7 delivered shared foundations, simulated workflows, consistent task snapshots and B/C handoff materials. Step 8 supports real detection: a primary box ≥0.60 automatically creates a task; lower confidence requires review. Business rules remain course simulations; road declarations and synthetic task points do not replace road verification.

2026-10-14: The [finalized business rules](Miscellaneous/BUSINESS_RULES_BASELINE.md) use `demo-rules-v2`, with P3/P2/P1=60/120/240 minutes. The [integration acceptance checklist](Miscellaneous/INTEGRATION_ACCEPTANCE_CHECKLIST.md) covers A's current checks and scenarios after B/C are ready. B/C integration is deferred; existing records retain their old rules.

## SECTION 1 : PROJECT TITLE

**RoadGuard: Road Damage Assessment and Four-Crew Maintenance Planning in Jurong**

| Item | Value |
| --- | --- |
| Course | Intelligent Reasoning Systems (IRS) Practice Module |
| Group | Group 7; repository team label: Group7 |
| Demonstration area | Jurong East and Jurong West, Singapore; frozen URA MP2025 boundary |
| Repair crews | Four simulated crews, sharing the NUS-ISS simulated dispatch origin outside the task area |
| Current phase | Persisted inspection/review/task workflow; opt-in real inference; planning pending |
| Course start date / batch code | 2026-08-17 / AIS08FT |

Repository name: `IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard`.

Private repository: [HUERJI-code / RoadGuard](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard).

`Group7` represents the confirmed group number; no separate formal team name has been supplied.

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

RoadGuard is a planned web application that connects road damage observations to maintenance decisions. An inspector submits a road image and its location. A YOLO detector identifies damage type, basic severity and confidence. A confidence gate sends uncertain results for human review, while accepted results pass through explicit priority rules and enter the maintenance queue.

The completed [30-epoch YOLO11n/YOLO11s comparison](Miscellaneous/VISION_30_EPOCH_COMPARISON.md) selects YOLO11s by validation mAP50-95. It improves recall at the fixed confidence threshold while increasing false positives and CPU latency; the current user-selected workflow accepts the primary detection at confidence >= 0.60; lower confidence requires review. This setting does not improve model accuracy. See [one-box responses and fields](Miscellaneous/INSPECTION_RESPONSE_FIELDS.md).

The subsequent [balanced Precision/Recall experiment](Miscellaneous/BALANCED_VISION_OPTIMIZATION.md) completed another 40 fine-tuning epochs and compared four validation candidates. The selected checkpoint reaches 50.5% Precision and 52.0% Recall at confidence 0.25 with correct eight-class, IoU 0.5 matching, versus 48.6% / 51.2% for the parent. The requested simultaneous 70% target remains unmet, and some damage types regressed. The local recommendation remains experimental and opt-in.

A group-built genetic algorithm (GA) will assign accepted tasks to four repair crews and determine their visit order. A greedy planner will provide a baseline using the same tasks, travel-time matrix and constraints. Evaluation will report travel time, urgent-task delay, workload balance, feasibility and computation time separately.

Repair tasks are limited to Jurong East and Jurong West. The maintenance department and tasks are simulated, with the real NUS-ISS location used as a shared simulated dispatch origin outside the task area; these are not official maintenance records or an actual NUS-ISS maintenance operation. Origin-to-task travel must be counted. RDD2022ES is the proposed image dataset. The proposal's GPT/RAG route explanation component remains planned and will use calculated route facts and reviewed project knowledge.

Measured vision results must be read with the corresponding experimental run and limitations. The project does not claim measured cost savings or operational readiness.

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official full name | Student ID | Work items / contribution | Email (optional) |
| --- | --- | --- | --- |
| TBD | TBD | TBD | |

Replace the placeholder with the confirmed team roster. Contributions must describe work actually completed. Prepare the submission roster using [member-github.example.txt](Miscellaneous/member-github.example.txt).

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

Two separate videos are required by the current course briefing:

| Video | Target duration | Content | Status |
| --- | --- | --- | --- |
| Promotion / use-case demonstration | 5 minutes | Business pain, value and working use cases | Planned |
| System design / technical explanation | 5 minutes | Architecture, reasoning methods and technical walkthrough | Planned |

See [Video/README.md](Video/README.md) for naming and recording requirements.

## SECTION 5 : USER GUIDE

Run the backend using the [backend installation and startup guide](SystemCode/backend/README.md), then open `/docs`. The [step 6 workflow guide](Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md) covers image uploads, review and task management. The separate [step 5 demo endpoints](Miscellaneous/DEMO_DETECTION_AND_RULES.md) still provide stateless previews. There is no frontend yet. Use the [API contract](Miscellaneous/API_CONTRACT.md) for the new record/request schemas and the [fixed DTO examples](SystemCode/contracts/README.md) for the original snapshots. See the [installation and user guide](ProjectReport/INSTALLATION_AND_USER_GUIDE.md) for the delivery boundary.

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

The [report outline](ProjectReport/REPORT_OUTLINE.md) reserves the sections required by the course. The final group report will be delivered as DOCX or PDF in `ProjectReport/`.

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
- [Implementation milestones](Miscellaneous/IMPLEMENTATION_PLAN.md)
- [Three-person work allocation and interface draft](Miscellaneous/TEAM_WORK_ALLOCATION.md)
- [Submission checklist and file naming](Miscellaneous/SUBMISSION_CHECKLIST.md)
- [Template and requirement provenance](Miscellaneous/TEMPLATE_SOURCE.md)
- [Member / GitHub submission file template](Miscellaneous/member-github.example.txt)

Development started from this course scaffold. The previous prototype has been abandoned at the project owner's request; its code and historical results are not part of this project baseline.
