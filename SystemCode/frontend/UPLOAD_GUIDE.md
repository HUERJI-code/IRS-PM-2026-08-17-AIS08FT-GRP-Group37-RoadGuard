# C step 4: Upload and results

Owner C; 2026-10-16. This step connects existing A endpoints without changing models, rules, database structure or A/B APIs.

## Usage

1. Open `/inspections/new` with “Live backend API”. The top-level read-only mock snapshot differs from the form’s mock detection: the former blocks writes, while the latter saves an explicit demo inspection through the real backend.
2. Select real image inference or mock detection. Demo scenarios come from `/demo/scenarios`; real requests omit scenario_id entirely. Real inference requires configured backend weights and dependencies.
3. Select one JPEG/PNG. Frontend checks a nonempty file, 8 MiB limit, decodability and 20 MP limit. Backend performs final safety/content validation.
4. Enter actual photo coordinates in WGS84 latitude/longitude and confirm the public-motor-road declaration. Backend validates the frozen Jurong boundary; frontend does not infer road eligibility. This step uses coordinate inputs; map selection is deferred to the map stage.
5. Successful upload navigates to `/inspections/{id}` and reads full inspection details; accepted inspections also load their task. Results support direct links and refresh.

## Routing and display

- accepted: show backend task, priority, repair duration, rule version and recommendation and automatic planning outcome. A failed planning attempt preserves the task and warns the user to retry through manual recalculation.
- pending_review: show pending status and review-workspace link. Review is implemented in step 5 ([guide](REVIEW_GUIDE.md)); no task is created before confirmation.
- no_detection: show no task and explain that no detection does not establish road safety.
- rejected: show the retained inspection read-only.

Only the single returned detection box is drawn. The server-normalised PNG is overlaid proportionally with SVG using image_width/height and original-pixel bbox_xyxy. The local original and nonexistent annotated images are not used. Image failure retains detection/task text. Inference mode, model version, auto-acceptance policy/manual review provenance and course-demo business rules are distinguished. Confidence is not described as accuracy.

## Retry and limitations

One upload retains File, metadata and Idempotency-Key. Processing disables the form and duplicate submission. An uncertain network outcome retains and locks the original inputs, allowing only the original request to be retried. Explicit input rejection allows correction and a new action/key. Upload waits up to 120 seconds without automatic retry; health/general reads retain the eight-second default.

After upload success, subsequent operations read the inspection ID. Detail/task failures retry GET only, never POST again. A failed task read retains inspection results. Results link to the review workspace. The backend automatically attempts paired planning for accepted uploads after task commit; the page displays its outcome.

Stay on the page while the outcome is uncertain; closing/refreshing triggers a browser leave warning. File and retry ID exist only in page memory and cannot survive refresh. Do not change source or navigate away and resubmit an unknown-outcome upload. Durable recovery would require an explicit persistence protocol rather than silently creating a new request.

## Stage validation

- Static checks, 43 tests and production build passed.
- Real HTTP with an isolated test database uploaded synthetic PNGs for high_confidence, low_confidence and no_detection. Each verified upload, same-key replay, details, PNG and linked task. Initial 201 and replay 200 created no duplicate tasks.
- Browser demo high-confidence upload displayed one box and a P2/120-minute task. At 390 pixels, no horizontal overflow occurred; image and overlay both measured 293×219.75.
- Added tests cover duplicate submission, original-key retry, read-only detail retry, task-read failure, demo fields, four statuses, image errors/limits, coordinates/road declaration and read-only mode.
- Synthetic images/demo detection were used. No real model ran; this is not vision-accuracy evidence. The isolated backend database left ordinary project data unchanged.
- Build succeeded with a >500 kB JS-chunk warning (about 512 kB, gzip 144 kB); route splitting may be added later.

At this stage, code remained local, uncommitted and unpushed. Step 5 review is now connected; see REVIEW_GUIDE.md.
