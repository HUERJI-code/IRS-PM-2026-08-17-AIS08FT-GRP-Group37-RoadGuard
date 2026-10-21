# RoadGuard dataset and eight-class label audit

Version 1.0; verified 2026-10-12; owner A.

This preserves Step 2's historical scope. See [Step 8 acceptance](STEP8_VISION_ACCEPTANCE.md) for 2026-10-13 full-content checks, EXIF quarantine, grouped splits and training evidence. Later results are not retroactively claimed as completed here.

Vision data uses **Juuso's Kaggle RDD2022ES version 1**. Release information and archive `classes.txt` independently verify eight IDs for A/B/C's shared dictionary. These are neither Singapore/Jurong field images nor repair priorities.

This step completed **source checks, full release-file inventory, eight-label confirmation and targeted sampling**. It had not downloaded the full dataset, counted all class frequencies, generated training splits or trained a model. This is A's preparation Step 2, not completion of overall foundation implementation.

## 1. Source and version

| Item | Verified result |
| --- | --- |
| Publisher/identifier | Juuso; `juusos/rdd2022es`; Kaggle ID `7353702` |
| Name | RDD2022ES, Severity Extended RDD2022 |
| Pinned version | Version 1, release field `2025-05-07T08:54:20.383Z` |
| Original source | RDD2022; ES publisher reports manual relabeling of four classes into eight |
| Countries | United States, India, Japan, Czech Republic; no Singapore |
| Archive | 2,611,933,018 bytes; uncompressed members total 2,740,407,610 |
| Directory | `combined_annotatedv2/`, mixed images/labels plus `classes.txt` |
| Format | JPG plus YOLO detection TXT; no published YAML or train/val/test directories found |
| Dictionary | [label_schema.json](../SystemCode/model/label_schema.json), `rdd2022es-v1-labels-1` |

Sources: [ES release](https://www.kaggle.com/datasets/juusos/rdd2022es), [Kaggle metadata](https://www.kaggle.com/api/v1/datasets/view/juusos/rdd2022es), [fixed v1 download](https://www.kaggle.com/api/v1/datasets/download/juusos/rdd2022es?datasetVersionNumber=1). ZIP byte-range reads retrieved directory information and a few members, not the whole local archive.

**Do not conflate RDD2022 and RDD2022ES.** Original RDD2022 has six countries/four classes, public Pascal VOC XML training labels and image-only competition test data. ES is another publisher's derivative with eight IDs/TXT. Original totals, IDs and competition splits are not ES properties. [Original project](https://github.com/sekilab/RoadDamageDetector)

## 2. Eight labels and IDs

English names/order below match `combined_annotatedv2/classes.txt`; project display names are maintained locally. IDs are fixed **0-7**. Display values were translated into English on 2026-10-19; source IDs/names remain unchanged.

| ID | Source English name | Project display name | Base family | Visual qualifier |
| --- | --- | --- | --- | --- |
| 0 | longitudinal crack | Longitudinal crack | D00 | unspecified |
| 1 | longitudinal crack wide | Wide longitudinal crack | D00 | wide |
| 2 | transverse crack | Transverse crack | D10 | unspecified |
| 3 | transverse crack wide | Wide transverse crack | D10 | wide |
| 4 | alligator crack | Alligator crack (network cracking) | D20 | unspecified |
| 5 | alligator crack sunken | Sunken alligator crack | D20 | sunken |
| 6 | pothole | Pothole | D40 | unspecified |
| 7 | pothole deep | Deep pothole | D40 | deep |

Sources: [ES release](https://www.kaggle.com/datasets/juusos/rdd2022es) and extracted `classes.txt`; original hash in [sample manifest](dataset-audit/rdd2022es-v1-sample-manifest.json). D00/D10/D20/D40 express family correspondence, not ES numeric IDs.

These are image labels. Verified release information supplies no millimeter/centimeter/field-measurement thresholds for `wide`, `sunken`, `deep`; classes do not establish measured crack width or pothole depth. Unqualified classes do not automatically mean minor damage.

**P1/P2/P3, business severity, service minutes, deadlines and confidence thresholds remain for the next business-rule step.** Historical High/P1 demo mappings are not native dataset labels. Keep eight training outputs; future rules may map them without silently merging/reordering labels.

## 3. Release inventory and anomalies

The complete v1 ZIP central directory was read with correct ZIP64 member lengths. These are **archive-directory counts**, not full decoding/content validation.

| Content | Count |
| --- | ---: |
| ZIP members | 51,200 |
| JPG images | 25,600 |
| Originals / `xmirror_` | 12,800 /12,800 |
| TXT total | 25,600 |
| `classes.txt` | 1 |
| Per-image TXT | 25,599 |
| Image/same-name annotation pairs | 25,598 |
| Zero-byte annotations | 8,317; one without image |
| Paired empty/nonempty annotations | 8,316 /17,282 |

Image country-prefix counts, including originals/mirrors:

| Prefix | Original | Mirror | Total |
| --- | ---: | ---: | ---: |
| Czech | 3,364 | 3,364 | 6,728 |
| India | 2,533 | 2,533 | 5,066 |
| Japan | 3,990 | 3,990 | 7,980 |
| United_States | 2,913 | 2,913 | 5,826 |

Pair anomalies below must be quarantined during preparation, preserving originals without automatic deletion/invented labels:

| File under `combined_annotatedv2/` | Problem | Preparation treatment |
| --- | --- | --- |
| `Czech_001003.jpg` | No matching TXT | Exclude provisionally; missing annotation does not establish no damage |
| `xmirror_Czech_001003.jpg` | No matching TXT | Quarantine with original |
| `India_001032.txt` | No matching JPG; extracted content confirmed empty | Record orphan, exclude from prepared data |

Removing mismatches gives **25,598 candidate pairs**, or 12,799 original/mirror groups. This is not final training size before full image decoding, box validation and near-duplicate handling.

Empty annotations mean no boxes in that file, not road safety. Source-checked/sampled empty negatives may be retained; do not add a no-damage class or silently keep only boxed images without describing sampling bias.

Full directory counts, directory hash and anomaly names: [audit](dataset-audit/rdd2022es-v1-audit.json). Full-archive SHA-256 was not yet available; directory hash must not be described as the entire dataset hash.

## 4. Annotation format and content sampling

Each nonempty line contains five fields:

```text
class_id x_center y_center width height
```

IDs are zero-based; the remaining values are center coordinates and width/height normalized to image size. Each line is one box; images may contain multiple boxes/classes. Training labels differ from future API pixel `bbox_xyxy` and require image-size conversion. [Ultralytics format](https://docs.ultralytics.com/datasets/detect/)

For example, archive `Czech_000004.jpg` is600x600 with annotation:

```text
1 0.225833 0.765833 0.288333 0.191667
```

This means class1, wide longitudinal crack, approximately pixel `(49,402,222,517)`. This is source annotation, not our prediction, and has no confidence field.

Targeted extraction: nine original/mirror groups (18 images),19 labels including orphan, and `classes.txt`: 38 files, about 1.93 MB. Coverage includes eight classes, four countries, empty labels, multiple objects and orphan labels.

| Actual check | Result |
| --- | --- |
| Integrity | All38 file lengths/ZIP CRC32 match; separate SHA-256 retained |
| Image decode | All18 decode; sample sizes600x600/720x720, without assuming fixed dimensions for all data |
| Labels | 30 boxes pass five-column, IDs0-7, finite-number, positive-size/boundary checks |
| Empty labels | Three: Czech original/mirror plus orphan `India_001032.txt` |
| Mirror labels | Nine groups retain class/count; maximum `x ->1-x` error <=`5x10^-7` |
| Mirror pixels | Mean absolute difference from horizontal original flip about 0.136-0.845 on 0-255 scale, not byte-identical |
| Visual review | Czech wide longitudinal, Japanese alligator/sunken, Indian deep-pothole and Japanese transverse samples checked for label meaning, not full-dataset accuracy |

Samples target classes/anomalies, **not random quality estimation**. Their class proportions are not full-data frequencies and cannot prove no mislabeled data/leakage. Samples, checks and hashes: [audit](dataset-audit/rdd2022es-v1-audit.json), [manifest](dataset-audit/rdd2022es-v1-sample-manifest.json).

## 5. Originals, mirrors and future splits

Every directory-listed original has an `xmirror_` partner. Nine extracted groups support horizontal mirroring, not validation of all mirror contents.

Future preparation must:

1. Strip leading `xmirror_` for known mirror-group IDs; e.g. `Japan_000003` and `xmirror_Japan_000003` share a group.
2. **Split groups before creating training directories/manifests.** Groups cannot cross train/val/test. Record proportions/seed at formal preparation; neither is frozen here.
3. Beyond mirrors, check exact/near duplicates and possible adjacent scenes; different filenames do not establish independence.
4. Prefer original-only val/test to avoid mirror double-counting; training may use originals/mirrors with random-flip use recorded. Confirm this evaluation choice during formal splitting.
5. Retain each source, group, country, hash, split/exclusion; report image/group/class-box counts and images per class.
6. Use val for thresholds/model selection; reserve test for final evaluation. Tuning thresholds after test results invalidates claims of independent testing.

Neither publisher ES splits nor project split files existed here. Randomly splitting all images is not evidence of leakage prevention.

## 6. Conflicting license information

Live queries found two inconsistent statements by the same publisher:

| Location | Recorded content |
| --- | --- |
| Kaggle API `licenseName` | **CC BY-NC-SA4.0** |
| Release body | **CC BY-SA4.0** |

Both require attribution and constrain sharing adaptations; **NC** additionally restricts commercial use. [BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/), [BY-SA](https://creativecommons.org/licenses/by-sa/4.0/)

Retain both statements without resolving the conflict or claiming commercial permission. Manage course data under the noncommercial statement for now. Verify publisher authorization before redistributing originals/adaptations or commercial use. Historical presentation attribution listing only CC BY-SA4.0 is incomplete; formal reports/reused images should disclose this difference. Historical slides were not changed this round.

Git retains audit prose, dictionary and small counts/hashes only. Extracted originals/labels/ZIP index remain in local research storage, outside committed project documents.

## 7. Team handoff and next steps

| Member | Available now | Do not infer at this stage |
| --- | --- | --- |
| A | Fixed IDs, English labels/display names, format, anomalies, mirror rules | Undefined priorities/durations/thresholds; full-data quality/model performance |
| B | Label meanings/stable keys for future Task inputs | Numeric IDs are not urgency; await A's calculated priority/service time |
| C | English display names/keys; no-detection/simulated-provenance explanations | deep is not measured depth; empty labels do not prove road safety |

Next A drafts class -> business severity/priority/service duration/deadline mappings with B. Full training preparation additionally needs full download/version/hash, all-image decoding/box checks, class statistics, near duplicates and grouped splits.

No training, inference, weights, transformation pipeline or business API was delivered here. `label_schema.json` was a shared static dictionary, not yet integrated into running services.
