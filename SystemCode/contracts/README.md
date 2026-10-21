# Fixed contract fixtures

Step 7 adds [planning/](planning/README.md): reproducible 10/15/20-task, empty-queue and unknown-service-time fixtures using a-task-query-v1 and canonical sources. These are maintained separately from the original a-dto-v1 fixtures below. See the [B/C handoff](../../Miscellaneous/BC_HANDOFF.md) for online query entry points, actual HTTP response exports and C's knowledge package.

A maintains this directory for B/C integration before business services are available. The only documentation for the first A DTO version is [API_CONTRACT.md](../../Miscellaneous/API_CONTRACT.md); executable definitions live in `backend/roadguard/schemas/`. This directory does not duplicate field definitions.

`examples/manifest.json` lists each fixture's DTO and declares `is_demo: true` for the entire set. Each file contains DTO JSON directly, suitable for Pydantic `model_validate_json` or fixed frontend responses. Inspections and tasks retain their own `is_demo`; error fixtures identify their source in `details`. Health/PlanningRevision retain their fixed field structure without extra demo fields; filenames and the manifest identify them as demonstrations, not live database state.

All inspections, image references, detections and tasks are synthetic demonstrations. `/demo-assets/synthetic-road.svg` is an illustrative resource URL; neither the resource nor an image service is implemented. Fixture confidences 0.96, 0.42 and 0.88 do not define the routing threshold. `medium` / `P2` / 45 minutes and `demo-unconfirmed-v1` are demonstration values, not confirmed rules; do not copy them into production mappings.

The snapshot associates one accepted inspection with one unique demo task; the other three inspections have no tasks. Health/revision refer to demo revision 1. No tasks were actually created, database revisions updated, images uploaded or detection executed. Follow the backend README and repository pytest configuration for validation commands and dependencies.
