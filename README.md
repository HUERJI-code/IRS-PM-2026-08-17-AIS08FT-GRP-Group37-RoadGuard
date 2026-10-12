# RoadGuard

**Status: repository scaffold for implementation review.**

Road damage assessment and maintenance planning for **Jurong, Singapore**, with **four repair crews**.

This repository follows the [IRS-PM project submission template](https://github.com/IRS-PM/Workshop-Project-Submission-Template). The directories and project plan are ready; application features and evaluation results are not yet implemented in this repository.

> 当前地理基线：维修任务限于 Jurong East 与 Jurong West，默认四队从 NUS-ISS 模拟起点出发。当前是供检查的正式开发仓库骨架。

## SECTION 1 : PROJECT TITLE

**RoadGuard: Road Damage Assessment and Four-Crew Maintenance Planning in Jurong**

| Item | Value |
| --- | --- |
| Course | Intelligent Reasoning Systems (IRS) Practice Module |
| Group | Group 7; repository team label: Group7 |
| Demonstration area | Jurong East and Jurong West, Singapore; frozen URA MP2025 boundary |
| Repair crews | Four simulated crews, sharing the NUS-ISS simulated dispatch origin outside the task area |
| Current phase | Repository setup and scope definition |
| Course start date / batch code | 2026-08-17 / AIS08FT |

Repository name: `IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard`.

Private repository: [HUERJI-code / RoadGuard](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard).

`Group7` represents the confirmed group number; no separate formal team name has been supplied.

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

RoadGuard is a planned web application that connects road damage observations to maintenance decisions. An inspector submits a road image and its location. A YOLO detector identifies damage type, basic severity and confidence. A confidence gate sends uncertain results for human review, while accepted results pass through explicit priority rules and enter the maintenance queue.

A group-built genetic algorithm (GA) will assign accepted tasks to four repair crews and determine their visit order. A greedy planner will provide a baseline using the same tasks, travel-time matrix and constraints. Evaluation will report travel time, urgent-task delay, workload balance, feasibility and computation time separately.

Repair tasks are limited to Jurong East and Jurong West. The maintenance department and tasks are simulated, with the real NUS-ISS location used as a shared simulated dispatch origin outside the task area; these are not official maintenance records or an actual NUS-ISS maintenance operation. Origin-to-task travel must be counted. RDD2022ES is the proposed image dataset. The proposal's GPT/RAG route explanation component remains planned and will use calculated route facts and reviewed project knowledge.

The project does not yet claim measured cost savings, trained-model accuracy or operational readiness.

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

The application is not runnable yet in this repository. Installation and startup instructions will be added and tested alongside implementation; see the [installation and user guide outline](ProjectReport/INSTALLATION_AND_USER_GUIDE.md).

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

All contributors and coding agents should first read the shared [project and agent collaboration rules (中文)](AGENTS.md). The file includes module boundaries, interface-change rules, validation requirements and a reusable agent kickoff prompt.

## SECTION 6 : PROJECT REPORT / PAPER

The [report outline](ProjectReport/REPORT_OUTLINE.md) reserves the sections required by the course. The final group report will be delivered as DOCX or PDF in `ProjectReport/`.

Required appendices include the proposal, functionality-to-course mapping, and installation/user guide. Individual reflections and peer evaluations are submitted confidentially through the individual Canvas assignment, following the current briefing.

## SECTION 7 : MISCELLANEOUS

- [Project and agent collaboration rules (中文)](AGENTS.md)
- [Feature branches, pull requests and CI (中文)](Miscellaneous/GITHUB_WORKFLOW.md)
- [Confirmed scope and open design decisions](Miscellaneous/PROJECT_SCOPE.md)
- [Jurong boundary and NUS-ISS simulated dispatch origin (中文)](Miscellaneous/JURONG_SCOPE_AND_DEPOT.md)
- [RDD2022ES version and eight-class label audit (中文)](Miscellaneous/DATASET_AND_LABEL_AUDIT.md)
- [Implementation milestones](Miscellaneous/IMPLEMENTATION_PLAN.md)
- [Three-person work allocation and interface draft (中文)](Miscellaneous/TEAM_WORK_ALLOCATION.md)
- [Submission checklist and file naming](Miscellaneous/SUBMISSION_CHECKLIST.md)
- [Template and requirement provenance](Miscellaneous/TEMPLATE_SOURCE.md)
- [Member / GitHub submission file template](Miscellaneous/member-github.example.txt)

Development starts from this scaffold. The previous prototype has been abandoned at the project owner's request; its code and historical results are not part of this project baseline.
