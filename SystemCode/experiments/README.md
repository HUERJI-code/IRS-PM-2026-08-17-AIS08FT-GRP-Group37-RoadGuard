# Experiments - planned

Routing (B): the runner, settings and recorded simulated-matrix results are in [routing/](routing/README.md).

Primary scenario: four crews, one fictional shared depot and synthetic tasks within the defined Jurong study area.

The proposal's initial task counts are 10, 15 and 20. For each scenario, compare GA with greedy using identical tasks, matrix, service times, shifts and feasibility constraints. Record fixed random seeds and repeat the stochastic GA across multiple seeds.

Record these metrics separately:

- Total travel time.
- Urgent-task delay under an explicitly defined lateness rule.
- Crew workload balance, including service time.
- Total completion time.
- Assigned/unassigned task counts and constraint violations.
- Algorithm runtime, separate from external API latency.

An optional crew-count sensitivity experiment may compare two, three and four crews while keeping the task set fixed. Four crews remains the default demonstration.

Before experimentation, specify GA settings, stopping criteria, objective weights and data provenance. Do not fill result tables with placeholders presented as measurements.
