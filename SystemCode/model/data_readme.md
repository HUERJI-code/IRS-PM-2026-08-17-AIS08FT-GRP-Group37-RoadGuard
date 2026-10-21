# RDD2022ES v1 local preparation

Owner: A; Step 8 data interface. The project owner runs the downloader; preparation scripts do not access the network.
Place the complete fixed version-1 ZIP at repository `Dataset/downloads/rdd2022es-v1.zip`,
then run from repository root using Python with Pillow installed:

```powershell
python SystemCode/model/data_pipeline.py prepare
```

All large files and generated manifests stay in Git-ignored `Dataset/`. The script hashes the archive,
checks fixed SHA-256 `3ceb9de3b7ca7083379e4fc62748bafcda0a82d1baf4627cf87891c9595fa775`
and size 2,611,933,018 bytes, safely extracts to `Dataset/raw/rdd2022es-v1/`, verifies fixed-version directory counts and eight names,
fully decodes each JPEG, checks mirror relationships and validates class IDs, finite numbers, positive box sizes and bounds on every annotation line.
Normalized-boundary tolerance `1e-6` only accommodates publisher rounding to six decimal places. Source files are neither repaired nor deleted.
The entire known missing-annotation `Czech_001003` group is quarantined; `India_001032.txt` is retained and recorded as an orphan annotation.
Other missing files, corrupt images, invalid annotations or broken mirror relationships save a failure audit and return nonzero without publishing YAML.
Empty annotations mean no annotated boxes, not road safety; no safe-road training class is added.

On 2026-10-13 the first real full-data run completed 25,600 full-image decode attempts and reported only
`India_000430.jpg` with EXIF orientation 8 and `India_004098.jpg` with orientation 3.
Both originals and their mirrors are 720x720; mirrors have orientation 1. Whether source annotations follow EXIF-rotated
coordinates is unverified. The project owner chose to quarantine both complete original/mirror groups without altering sources.
Only these fixed v1 members with matching SHA-256 and orientation can be excluded for
`exif_orientation_unverified_labels`; full decoding and label validation still run.
Unknown orientations or changed content of known members fail preparation. The owner retained the first failed audit at
`Dataset/audits/initial-exif-failure/`; later full reruns are recorded separately.

| Member | EXIF orientation | Fixed SHA-256 |
| --- | ---: | --- |
| `India_000430.jpg` | 8 | `01c4ef927c8193a209e1169f8bc937ad16764c1b2d756ba0a5c9d7332ea3fa9c` |
| `xmirror_India_000430.jpg` | 1 | `c4bfebccb2f4a6bda5a9891c18d6a2bcc43689395e2a634cd1c118ae15c6c167` |
| `India_004098.jpg` | 3 | `219984707789be5cab1418ae6804227487b08b1eae5b158cf88dc44b26e73c2a` |
| `xmirror_India_004098.jpg` | 1 | `b3f2acdf5013819d14f6b9f503a3dfa2ae155eddee6b36aa0424e8d48f9feb35` |

First group originals with `xmirror_` partners, byte-SHA-256 duplicates and decoded-pixel duplicates. Then screen original-image
near-duplicate candidates using a mirror-aware 64-bit dHash BK-tree (distance at most 4), merging conservatively when 16x16 RGB thumbnail
RMSE <=6. Accepted near-duplicate edges are recorded in `audit.json`.
These heuristics may overgroup or miss nearby scenes; do not claim every near duplicate/adjacent frame has been removed.
Capture-sequence/location metadata is unavailable; unidentified scene correlation remains an evaluation limitation.

Stratify by merged group country sets, using fixed seed 42 and group-level 70/15/15 proportions allocated by largest remainder;
this is a provisional project protocol. Cross-country duplicate groups form their own country-set stratum without splitting groups.
Training uses originals and existing mirrors; validation/test use originals only. Training must set `fliplr=0.0`.
Small country-set strata may lack validation/test groups; inspect actual distributions. Even class stratification is not guaranteed.

Outputs under `Dataset/prepared/`:

- `data.yaml`: parseable YAML with eight `names` using canonical source English names.
- `images/{train,val,test}` and `labels/{train,val,test}`: hard links preferred; otherwise copy and verify SHA.
- `manifest.jsonl`: source path, country, original group, final duplicate group, SHA, label boxes,
  actual split, assigned split and exclusion reason for each original image. Orphan labels appear in audit `exclusions`.
- `audit.json`: download hash, full verification, quarantine, duplicate grouping/limitations, complete class statistics and leakage assertions.
- `split_summary.json`: per-split image/group/country/empty-annotation/class-box counts and images containing each class.

Preparation directories cannot be overwritten. Before rerunning, the operator must preserve the old directory and use a new Dataset root
(`--archive`, `--dataset-root`, CLI-confined to repository `Dataset/`), or rename the old prepared directory.
Raw/prepared hard links share content; training tools must read only and never modify labels/images.
Existing raw extraction may be reused, but every member is compared again with ZIP content rather than trusting old extraction markers.

These data are not Jurong field imagery. Source and BY-SA body/BY-NC-SA metadata discrepancies remain governed by the
[dataset audit](../../Miscellaneous/DATASET_AND_LABEL_AUDIT.md).
`python -m pytest SystemCode/tests/test_data_pipeline.py -q` uses synthetic ZIPs,
without downloading real data or training models.
