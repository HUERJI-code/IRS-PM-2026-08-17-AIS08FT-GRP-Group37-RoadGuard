# C step 8: Jurong map and four-crew routes

2026-10-17; owner C. Steps 7–8 were restored to the original project and browser-verified; see BROWSER_ACCEPTANCE.md.

## Features

/routes adds a GA/Greedy map selector using the repository’s frozen Jurong East/West GeoJSON and NUS-ISS depot file. No replacement boundary download, polygon simplification or paid map service is used.

The north-up SVG geographic diagram supports zoom, four-direction panning and full-area/depot reset. Default bounds include the whole service area, external depot and saved stops. Four crews use stable blue/orange/purple/green colours plus text/numbers, so colour is not the only cue.

Lines begin at the saved depot and connect stops sorted by stops.sequence. A return line is added only when saved settings require it; return policy and original stops arrays are unchanged. Idle/unavailable crews remain visible without invented routes.

Map points, crew legends and stop lists support mouse/keyboard selection linked to details. Overlapping points can be selected individually from the list. Details show saved coordinates, priority, previous-leg travel, repair minutes, arrival/completion, crew total travel, return and finish time. Times use Asia/Singapore. Links open current tasks and explain that they may differ from the saved plan.

All unassigned tasks retain backend reasons. The current contract does not save their coordinates: plot only when the active snapshot input_revision matches the plan and contains that task; otherwise show unavailable location without mixing old/new coordinates.

Without a plan, show only area/depot. Stale/read-failure notices sit beside the map. Algorithm switching performs no writes and does not imply two latest plans share a run. GA/Greedy comparison was the next stage.

## Geography and provenance

- Boundary: Miscellaneous/geography/jurong-boundary-mp2025.geojson, jurong-je-jw-mp2025-v1.
- Depot: Miscellaneous/geography/nus-iss-depot.geojson. Routes use saved plan depot coordinates; default bounds retain the frozen reference point.
- GeoJSON uses [longitude, latitude]; business records use latitude/longitude. A local cosine longitude correction is used only for drawing, never eligibility or travel calculation.
- URA/data.gov.sg provenance, retrieval date 2026-10-12 and Singapore Open Data Licence links remain visible. Planning boundaries do not establish maintenance authority; the depot is a building-address reference.
- geometry is currently null. Routes are explicitly stop-order diagrams, not road navigation, even when matrix data comes from Google.

## Files and dependencies

Added src/map/geography.ts, src/components/RouteMap.tsx and RouteMap.test.tsx; updated RoutesPage, integration tests, styles and docs. No new dependencies. Vite/Vitest allow only the shared geography directory and existing label file for development reads, retaining strict access and default sensitive-file blocks rather than exposing the repository.

## Validation and limitations

Twelve map tests and one algorithm-switch integration test cover all boundary/depot bounds, coordinate direction, stable colours, sorted lines, returns, keyboard/list interaction, final crew states, unassigned-coordinate revisions, absent plans, stale/failure notices and matrix source.

Browser and 390×844 checks completed (BROWSER_ACCEPTANCE.md). No real Google/model/paid-service calls, A/B changes, boundary edits or ordinary business-data changes.

## Delivery

Steps 2–8 are in the original project, uncommitted/unpushed at this stage. The old accumulated patch was applied and must not be applied again. Step 9 same-run comparison is complete (COMPARISON_GUIDE.md); step 10 knowledge retrieval follows.

## Final checks

2026-10-17: lint, 100 tests in eight files and build passed. JS 670.51 kB, gzip 179.93 kB; >500 kB warning retained. The working copy’s two GeoJSON files matched the originals byte for byte.
