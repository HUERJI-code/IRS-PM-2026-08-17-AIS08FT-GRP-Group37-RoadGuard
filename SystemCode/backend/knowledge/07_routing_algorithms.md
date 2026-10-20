# Greedy and genetic-algorithm routing

document_id: `rg-kb-routing`; document_version: `1`; owner: `A`.

<a id="routing-input"></a>
## Implemented planning and shared constraints

classification: `confirmed_project_fact`. citation_id: `rg-kb-routing#routing-input`.

Both Greedy and the custom genetic algorithm (GA) are implemented. PlanningService reads all active tasks and all four configured crews in one database snapshot. Saved task priority and service_minutes are inputs; the planner does not infer them again from photos or substitute today's rule table. Only available crews receive tasks. Both algorithms use the same travel matrix, depot, settings and RoutingProblem evaluator.

Each input task must appear exactly once, either in a crew's ordered stops or in unassigned_tasks. Unknown service duration, inaccessible travel and shift limits are constraints, not permission to drop tasks silently. All available crews begin at the same depot at planning_start_at. This is static replanning from a common start; there is no live vehicle tracking, in-transit dispatch or task time-window model.

Sources: [src-routing-service](../roadguard/routing/service.py), [src-routing-models](../roadguard/routing/models.py), [src-routing-evaluation](../roadguard/routing/evaluation.py).

<a id="routing-demo-settings"></a>
## Current demo configuration

classification: `demo_assumption`. citation_id: `rg-kb-routing#routing-demo-settings`.

Configuration `b-routing-demo-v1` uses return_to_depot=true and a limited 480-minute shift per crew, including travel and service. An explicit unlimited shift is a different experiment. The shared project configuration still has return_to_depot=null/pending confirmation; the executable routing demo selects true independently and does not convert null to false. These choices and the objective weights are not approved operational policy.

The default `simulated_haversine_v1` matrix estimates great-circle distance times a 1.3 detour factor at 30 km/h, rounded to one decimal minute. Optional Google Routes uses DRIVE and TRAFFIC_UNAWARE. It supplies travel estimates, not verified road permission or a live-traffic guarantee. A Google failure reports an error and saves no plans; it does not silently switch to simulation. Routes currently have geometry=null; displayed straight lines are schematic.

Sources: [src-routing-config](../../config/routing.example.json), [src-project-config](../../config/project.example.json), [src-routing-matrix](../roadguard/routing/matrix.py), [src-google-matrix](../roadguard/routing/google_matrix.py), [src-routing-service](../roadguard/routing/service.py), [src-routing-models](../roadguard/routing/models.py).

<a id="routing-objective"></a>
## Priority-first objective and metric meanings

classification: `demo_assumption`. citation_id: `rg-kb-routing#routing-objective`.

The shared `b-objective-v1` evaluator minimizes the lexicographic tuple
`(unassigned_P1, unassigned_P2, unassigned_P3, J)`.
Earlier components take precedence: a lower scalar cost cannot compensate for leaving an extra P1 unassigned.

`J = 1.0 * makespan_minutes + 0.2 * total_travel_minutes + 0.5 * workload_std_minutes + 0.5 * priority_weighted_completion_minutes`.
Priority completion weights are P1=3, P2=2, P3=1. This is a demonstration weighted time objective, not monetary cost, distance, an accuracy score or solely travel time.

Makespan is the latest crew finish; return travel counts when enabled. Total travel includes depot legs. Workload standard deviation uses available crews' travel plus service, includes idle available crews at zero, and excludes unavailable crews. Priority-weighted completion is the weighted mean of assigned tasks' completion times relative to planning_start_at; it is not lateness. Lateness depends on due_at. When no assigned task has a deadline, lateness is null, not proven zero. Report assigned/unassigned counts and their priorities before scalar objective comparisons.

Sources: [src-routing-config](../../config/routing.example.json), [src-routing-evaluation](../roadguard/routing/evaluation.py), [src-routing-models](../roadguard/routing/models.py).

<a id="routing-greedy"></a>
## Deterministic Greedy baseline

classification: `confirmed_project_fact`. citation_id: `rg-kb-routing#routing-greedy`.

Greedy selects the earliest-free available crew. For that crew it chooses a feasible remaining task by priority P1 before P2 before P3, then shortest travel from its current location, then snapshot order. A crew stops when it has no feasible task. This is not a nearest-neighbour-only algorithm and is not guaranteed globally optimal. It has no random seed and shares GA's constraints and evaluator.

Sources: [src-routing-greedy](../roadguard/routing/greedy.py), [src-routing-evaluation](../roadguard/routing/evaluation.py).

<a id="routing-ga"></a>
## GA encoding, operators, defaults and stopping

classification: `confirmed_project_fact`. citation_id: `rg-kb-routing#routing-ga`.

The chromosome has an order permutation of schedulable tasks and an owner index assigning each task to an available crew. Each crew visits its owned tasks in permutation order. Tournament selection chooses parents; order crossover (OX) combines permutations and uniform crossover combines owners. Mutation chooses swap, segment reversal, crew reassignment or relocation. Elitism retains the best candidates.

Current configured defaults: population_size=60, max_generations=300, patience_generations=80, crossover_rate=0.9, mutation_rate=0.3, tournament_size=3, elite_count=2. Stopping occurs at the generation limit or patience limit. Randomness is supplied by a local seeded random generator. Reproduction needs the same input, matrix, settings, code and parameters, not a seed alone.

The experimental `ga.seed_with_greedy=false` configuration allows pure-GA comparisons. The online PlanningService overrides it with `planning_service.seed_with_greedy=true` and ga_seed=1. Greedy initialization plus elitism preserves a candidate no worse than Greedy under the shared lexicographic evaluator on the same input. It does not guarantee a strict improvement, less travel in every run, faster computation, or the global optimum. Read the saved plan's algorithm_parameters and random_seed when explaining a particular run.

Sources: [src-routing-config](../../config/routing.example.json), [src-routing-ga](../roadguard/routing/ga.py), [src-routing-service](../roadguard/routing/service.py), [src-routing-evaluation](../roadguard/routing/evaluation.py).
