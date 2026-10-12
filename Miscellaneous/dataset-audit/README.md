# RDD2022ES 第 1 版核验记录

说明见[数据集与标签核对](../DATASET_AND_LABEL_AUDIT.md)。这些文件记录 2026-10-12 的来源、全量 ZIP 目录检查和定向样本检查，不是训练集或模型结果。

| 文件 | 用途 |
| --- | --- |
| [rdd2022es-v1-audit.json](rdd2022es-v1-audit.json) | 来源版本、许可差异、目录计数、配对异常、样本检查及未完成项目 |
| [rdd2022es-v1-sample-manifest.json](rdd2022es-v1-sample-manifest.json) | 抽取的 38 个发布包成员的大小、CRC32 和 SHA-256；按原始解压字节计算 |
| [label_schema.json](../../SystemCode/model/label_schema.json) | 已核验的 0～7 标签编号、来源名称及项目显示名 |

全量目录核验不等于全量图片／标注内容核验。样本有意覆盖八类和异常，不能用其比例推断整个数据集的类别分布。CRC32 用于检查抽取内容与目录记录一致，不替代完整压缩包的 SHA-256。

数据来源：[Juuso / RDD2022ES](https://www.kaggle.com/datasets/juusos/rdd2022es)。发布者正文写 CC BY-SA 4.0，元数据标注 CC BY-NC-SA 4.0；差异尚未解决，详见主文档。原图和原始标签未加入仓库。
