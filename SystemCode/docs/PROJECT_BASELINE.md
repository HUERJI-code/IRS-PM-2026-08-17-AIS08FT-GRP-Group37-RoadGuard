# RoadGuard project baseline

## 1. Scope and delivery

RoadGuard is the Group 37 course prototype for Jurong East and Jurong West, Singapore. Four simulated repair crews share the NUS-ISS simulated origin outside the task area. Frozen URA MP2025 polygons validate task coordinates; road eligibility remains user-declared and the depot vehicle entrance remains unverified. This is not an official maintenance operation.

The implemented stack is React, FastAPI, SQLite, YOLO11s/RDD2022ES, group-built GA and Greedy planning, local ChromaDB/E5 retrieval and optional server-side GPT evidence selection. Maps are schematic. The backend owns authorized saved facts; static knowledge cannot establish today's tasks, routes or completed actions.

## 2. Inspection and business rules

An upload returns at most one primary damage box. A primary raw confidence at least 0.60 automatically creates one task; lower confidence requires review, and no detection creates no task. Confidence is not calibrated accuracy. Raw detection evidence and the frozen rule snapshot remain available. Review corrections use that snapshot and repeated confirmation must not duplicate tasks.

The eight label meanings remain fixed. demo-rules-v2 maps P3/P2/P1 to 60/120/240 service minutes. Severity, priority and service times are course assumptions, not engineering standards, measured repair times or deadlines. Image-type metrics and box-detection metrics are distinct; the requested simultaneous 70% targets remain unmet. Validation confirmation is not an independent local test.

## 3. Planning and assistant boundaries

GA and Greedy use identical task/crew snapshots, travel matrices and constraints. Accepted uploads and review confirmation/correction attempt paired planning after task commit. Planning failure preserves the task and previous stale plans. Accepted replay or manual recalculation can recover; there is no durable background recovery worker. Completion, cancellation and crew changes still require explicit recalculation.

The routing demo configures a 480-minute shift, return to depot and objective weights. Operational approval and calibration of shifts, return policy, weights, crew capabilities, engineering mappings, measured service times and deadlines remain outstanding. due_at=null supplies no deadline. Priority-weighted completion is not lateness. Unknown duration and unreachable travel are not zero. No plan is not a valid empty plan.

Route answers must identify the saved plan, input revision, crew routes, stop order, unassigned tasks, metrics, provider and staleness. Comparisons require compatible saved plans from the same calculation with matching tasks, matrix and settings; travel-saving claims also require identical assigned task sets. Synthetic matrices and straight map lines do not establish measured road travel. Without relevant facts, return insufficient data.

Assistant crew availability, task reassignment and cancellation require structured preview and explicit confirmation, version checks and existing business services. Static text cannot claim an action succeeded. Natural language cannot invent tasks, priorities, deadlines or service durations. Unrelated questions receive scope guidance; direct model configuration answers do not establish model execution or consume GPT quota. Broad semantic reliability remains unverified despite targeted accepted cases.

## 4. Reproducibility and interfaces

One backend owns shared SQLite transactions. B reads A's consistent task snapshots; C reads saved facts and calls A/B services. IDs are strings, JSON uses snake_case, WGS84 coordinates use latitude/longitude, travel and service use minutes, and timestamp storage is timezone-aware UTC. Preserve explicit null/empty/zero distinctions and structured errors.

Keep original and related augmented images within one split; never tune on test data. Dataset images are not proven to originate in Jurong. Preserve the publisher's conflicting BY-SA text and BY-NC-SA metadata. Retain failed or infeasible experiment results, parameters, seeds, environment and code identity. Distinguish algorithm runtime, API waiting, travel and completion; measured monetary savings have not been established.

See [scope](../../Miscellaneous/PROJECT_SCOPE.md), [API contract](../../Miscellaneous/API_CONTRACT.md), [rule baseline](../../Miscellaneous/BUSINESS_RULES_BASELINE.md), [routing experiments](../experiments/routing/README.md), [vision experiments](../experiments/vision/README.md), and [installation guide](INSTALLATION_AND_USER_GUIDE.md) for authoritative details and retained evidence.
