# RoadGuard

Road damage assessment and maintenance planning for **Jurong, Singapore**, connecting image inspections, repair decisions and route planning for **four repair crews**.

This public repository contains the application, project report, demonstration videos and supporting documentation. It follows the [IRS-PM project submission template](https://github.com/IRS-PM/Workshop-Project-Submission-Template).

## SECTION 1 : PROJECT TITLE

**RoadGuard: Road Damage Assessment and Four-Crew Maintenance Planning in Jurong**

| Item | Value |
| --- | --- |
| Course | Intelligent Reasoning Systems (IRS) Practice Module |
| Group | RoadGuard · Group 37 |
| Project area | Jurong East and Jurong West, Singapore |
| Repair crews | Four crews, with NUS-ISS as the simulated dispatch origin |
| Course start date / batch code | 2026-08-17 / AIS08FT |

Repository: [HUERJI-code / RoadGuard](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard).

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

Reporting a damaged road is only the first step in arranging a repair. The evidence must be assessed, repair work prioritised and tasks assigned to crews. RoadGuard brings these steps into a shared workflow so that inspectors, dispatchers and field crews can follow each task from submission to completion.

- **Inspect and review:** An inspector uploads a road image and location. A trained YOLO model returns one primary damage detection. Confidence of at least 60% automatically creates a repair task; lower-confidence detections require dispatcher review. Images with no detection create no task. Project rules assign severity, priority and estimated repair time.
- **Plan and adjust:** A genetic algorithm assigns tasks and visit order across four crews, with a Greedy planner for comparison. Accepted uploads and approved reviews automatically trigger a planning attempt. Dispatchers can review routes, move or cancel tasks, and update crew availability. These later changes require recalculation; confirmed crew assignments are retained. If automatic planning fails, the task remains saved and planning can be retried manually.
- **Carry out repairs:** Each crew has a mobile-friendly workspace showing its own route and assigned tasks, which it can mark as complete. Account permissions separate inspector, dispatcher and crew responsibilities.
- **Ask about the project:** The route assistant uses ChromaDB and E5 embeddings to retrieve project knowledge, alongside facts from saved plans. Optional GPT integration provides answers with checked citations and expandable sources.

The application uses a React frontend, a FastAPI backend and SQLite storage. Travel estimates can come from geographic-distance simulation or an optional Google road-network provider.

RoadGuard is a student project prototype. Repair durations and crew operations are simulated, model recognition still requires improvement, and some assistant questions may be declined by evidence or context checks. The project does not claim measured time or cost savings. The [final report](ProjectReport/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard-Group-Report.pdf) presents the evaluation results and limitations.

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official full name | Student ID | Work items / contribution |
| --- | --- | --- |
| Hu Erji | A0305480L | Dataset and label verification; YOLO model training, optimisation, evaluation and backend integration; business rules; shared backend; authentication; system integration and later interface refinement |
| Yan GuanTing | A0305485B | Four-crew Greedy/GA planning, crew and plan persistence, Google matrix provider and routing experiments |
| Wu TaoYi | A0356972M | Frontend foundation and workflow pages, map/comparison integration and the retrieval/confirmed-change assistant |

The submission roster and GitHub information are in [member-github.txt](ProjectReport/member-github.txt).

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

| Video | Content | Duration |
| --- | --- | --- |
| [Project introduction and use-case demonstration](Video/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard-promotion.mp4) | Background, business value and application walkthrough | 8m32s |
| [System design and technical explanation](Video/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard-system.mp4) | Architecture, reasoning methods and implementation | 4m55s |

The course target is five minutes per video; the promotion recording exceeds this target.

## SECTION 5 : USER GUIDE

Start with the [installation and user guide](SystemCode/docs/INSTALLATION_AND_USER_GUIDE.md). It covers dependencies, local account creation, startup commands and the main workflows.

- Frontend: `http://127.0.0.1:5173`
- Interactive API documentation: `http://127.0.0.1:8000/docs`
- Assistant setup: [ChromaDB and embeddings](SystemCode/backend/roadguard/assistant/VECTOR_RETRIEVAL.md). GPT answers also require server-side API configuration.

Accounts are created locally; the repository does not supply shared login credentials or a populated application database. Datasets, vector databases and model caches are excluded from Git.

```text
SystemCode/       Application, configuration, tests, experiments and user documentation
ProjectReport/    Final report PDF, original proposal PDF and member-github.txt
Video/            System and promotion recordings
Miscellaneous/    Runtime geography, contracts and supporting evidence
```

## SECTION 6 : PROJECT REPORT / PAPER

- [Final group report](ProjectReport/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard-Group-Report.pdf): project design, implementation, evaluation and conclusions, with the user guide, proposal and course mapping in the appendices.
- [Submitted project proposal](ProjectReport/RoadGuard_ProjectProposal.pdf).

## SECTION 7 : MISCELLANEOUS

- [Project scope and dispatch location](Miscellaneous/JURONG_SCOPE_AND_DEPOT.md)
- [Backend guide](SystemCode/backend/README.md) and [frontend guide](SystemCode/frontend/README.md)
- [API contract](Miscellaneous/API_CONTRACT.md) and [account permissions](Miscellaneous/ACCOUNT_ROLES.md)
- [Vision model and training documentation](SystemCode/model/README.md)
- [Routing evaluation](SystemCode/experiments/routing/README.md)
- [Assistant knowledge documentation](SystemCode/backend/knowledge/README.md)
- [Course functionality mapping](SystemCode/docs/COURSE_MAPPING.md)
- [Additional technical records](Miscellaneous/README.md)
