# 八类标签与解释限制

document_id：`rg-kb-labels`；document_version：`2`；owner：`A`。

<a id="label-table"></a>
## 中央标签字典

classification：`confirmed_project_fact`。citation_id：`rg-kb-labels#label-table`。

唯一标签字典为 `rdd2022es-v1-labels-1`，来源 Juuso 的 `juusos/rdd2022es` 第 1 版，包内 `combined_annotatedv2/classes.txt`。本包复核仓库中已核验的编号与名称，没有重新下载或宣称全量训练数据质量通过。八类 ID 为 0～7；基础 RDD2022 的 D00/D10/D20/D40 只是损坏族代码，不能替代八类编号。

| class_id | source_name | label_key | 中文显示 | 基础族代码 | 视觉限定词 |
| --- | --- | --- | --- | --- | --- |
| 0 | longitudinal crack | longitudinal_crack | 纵向裂缝 | D00 | unspecified |
| 1 | longitudinal crack wide | longitudinal_crack_wide | 宽纵向裂缝 | D00 | wide |
| 2 | transverse crack | transverse_crack | 横向裂缝 | D10 | unspecified |
| 3 | transverse crack wide | transverse_crack_wide | 宽横向裂缝 | D10 | wide |
| 4 | alligator crack | alligator_crack | 龟裂（网状裂缝） | D20 | unspecified |
| 5 | alligator crack sunken | alligator_crack_sunken | 下陷龟裂 | D20 | sunken |
| 6 | pothole | pothole | 坑洞 | D40 | unspecified |
| 7 | pothole deep | pothole_deep | 深坑洞 | D40 | deep |

来源：[src-label-schema](../../model/label_schema.json)。

<a id="label-limits"></a>
## 标签不是工程测量

classification：`confirmed_project_fact`。citation_id：`rg-kb-labels#label-limits`。

`wide`、`sunken`、`deep` 是来源数据集的视觉类别描述，不是量测的裂缝宽度、沉陷/坑洞深度或结构诊断。没有限定词的类别也不证明损坏轻微。标签字典不能直接提供 severity、priority、service_minutes 或 due_at；当前映射只在演示规则中定义，不能说来自数据集或正式工程标准。训练划分、真实推理和逐类指标必须引用对应模型版本的实际交付证据，不能从标签字典推断。

来源：[src-label-schema](../../model/label_schema.json)、[src-demo-rules](../../config/demo_rules.example.json)、[context-scope](../../../Miscellaneous/PROJECT_SCOPE.md)。
