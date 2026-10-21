# Eight labels and interpretation limits

document_id: `rg-kb-labels`; document_version: `3`; owner: `A`.

<a id="label-table"></a>
## Canonical label dictionary

classification: `confirmed_project_fact`. citation_id: `rg-kb-labels#label-table`.

The sole label dictionary is `rdd2022es-v1-labels-1`, from version 1 of Juuso's `juusos/rdd2022es`, member `combined_annotatedv2/classes.txt`. This package rechecks IDs and names already verified in the repository; it neither redownloads data nor claims full training-data quality acceptance. IDs are 0-7. Base RDD2022 D00/D10/D20/D40 are damage-family codes, not substitutes for these eight class IDs.

| class_id | source_name | label_key | English display | Base family code | Visual qualifier |
| --- | --- | --- | --- | --- | --- |
| 0 | longitudinal crack | longitudinal_crack | Longitudinal crack | D00 | unspecified |
| 1 | longitudinal crack wide | longitudinal_crack_wide | Wide longitudinal crack | D00 | wide |
| 2 | transverse crack | transverse_crack | Transverse crack | D10 | unspecified |
| 3 | transverse crack wide | transverse_crack_wide | Wide transverse crack | D10 | wide |
| 4 | alligator crack | alligator_crack | Alligator crack (network cracking) | D20 | unspecified |
| 5 | alligator crack sunken | alligator_crack_sunken | Sunken alligator crack | D20 | sunken |
| 6 | pothole | pothole | Pothole | D40 | unspecified |
| 7 | pothole deep | pothole_deep | Deep pothole | D40 | deep |

Sources: [src-label-schema](../../model/label_schema.json).

<a id="label-limits"></a>
## Labels are not engineering measurements

classification: `confirmed_project_fact`. citation_id: `rg-kb-labels#label-limits`.

`wide`, `sunken` and `deep` are visual categories in the source dataset, not measured crack widths, subsidence/pothole depths or structural diagnoses. An unqualified category does not prove minor damage either. The label dictionary does not directly provide severity, priority, service_minutes or due_at. Current mappings are defined only by demo rules, not the dataset or formal engineering standards. Cite actual delivery evidence for the relevant model version when discussing training splits, real inference or per-class metrics; these cannot be inferred from the label dictionary.

Sources: [src-label-schema](../../model/label_schema.json), [src-demo-rules](../../config/demo_rules.example.json), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md).
