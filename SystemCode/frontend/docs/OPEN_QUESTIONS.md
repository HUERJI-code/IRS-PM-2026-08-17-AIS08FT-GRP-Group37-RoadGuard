> Archive: retains the 2026-10-15 planning baseline/open items. Steps 1–9 are now implemented; README, VALIDATION.md and COMPARISON_GUIDE.md define actual validation. Steps 10–14 remain pending.

# RoadGuard · C step 1: Open coordination items

2026-10-15; main `f8a2cf37de91c09d86ec14e6cbd6045e83e421f8`. This list was prepared for A/B discussion, not sent to other members or confirmed by the team.

| ID | Issue/evidence | Owner | C proposal/acceptance | Blocking scope |
|---|---|---|---|---|
| D01 | Allocation section 7 says B pending, upload returns InspectionMutation and crew save recalculates; code differs | A shared docs, B behaviour | Document four-field upload then details, crew save then explicit recalculation; current schemas/examples | Not skeleton; update before integration |
| D02 | knowledge qa-03 requires all real nonempty detections reviewed, conflicting with primary auto-acceptance; some knowledge says B pending | A content, C index | Correct content/answers, bump package/hash, rebuild index; explain old records by frozen versions | Formal indexing/assistant factual acceptance |
| D03 | Boundaries in Miscellaneous/geography; labels in SystemCode/model/label_schema.json; no config HTTP API | A source, C consumer | Generate static frontend assets from central files with version/hash rather than copied rules; A freezes any new API. Show area/depot without plan | Decide before map/label implementation, not navigation |
| D04 | Return policy unconfirmed; B demo uses return=true/480-minute shift | A decision, B configuration, C display | Explicit demo assumptions from RoutePlan.settings; update shared config/knowledge after confirmation | Not demo; blocks operational-policy claims |
| D05 | CrewService.update checks crew version only; external global precheck creates race | B service, A transactions, C orchestration | Check preview input_revision and crew record_version within update transaction; reject concurrent task changes; C never writes A/B tables | Assistant confirmation writes |
| D06 | Recalculation has no request_id; crew save can succeed while planning fails | B idempotency, C persistence, A schema/migration | Freeze execution ID/stages/recovery; duplicate confirm never repeats saves/plans; query partial success and retry missing stages only | Confirmation/recovery |
| D07 | Four assistant routes unregistered; no independent status/recovery read; DTO/errors unfrozen | C proposal, A contract, B service review | Review API_MAPPING section 5; define querying/expiry/concurrent confirm-cancel/results/provenance; valid mocks/contract tests | Assistant live integration, not ordinary pages |
| D08 | Two latest plans cannot prove same matrix; RoutePlan lacks batch/hash, matrix time only in recalculation | B output, C comparison | Pair IDs from one response initially; persisted batch/matrix IDs for cross-session comparison | Not current-session comparison; blocks unsupported fairness claims |
| D09 | Main app has no CORS | C development, A deployment | Local /api proxy; production same-origin proxy or A-approved origins; never disguise failure as empty | Step 2 |
| D10 | Historical fixtures differ from current HTTP; upload lacks input_revision; real business is_demo remains true | A examples, C types/mocks | Build current-schema mocks in step 3; inference provenance by mode; read detail/task revisions after upload | Step 3 |

## Work that can proceed

Step 2 can build React skeleton, six navigation categories, shared state and API proxy. Step 3 can implement the seventeen existing APIs and mocks. Until D03 is resolved, reserve a static-source adapter without inventing business data.

Assistant UI/read-only design can proceed. Until D02/D05/D06/D07 are resolved, do not claim reliable confirmed crew changes/recovery.

## Step 1 acceptance

| Check | Result at this stage |
|---|---|
| Six page categories, entries/transitions | Documented |
| Fields traced to APIs/central assets | Documented; asset delivery explicitly open |
| A/B implementation separate from C proposal | Seventeen existing endpoints, four assistant drafts |
| Normal/empty/failure/concurrency | Documented with illustrative JSON |
| Team approval of new endpoints | Not claimed; awaiting owners |
| Runtime tests/page implementation | Not performed; outside this documentation delivery |
| Repository changes | None then; documents in Codex outputs |
