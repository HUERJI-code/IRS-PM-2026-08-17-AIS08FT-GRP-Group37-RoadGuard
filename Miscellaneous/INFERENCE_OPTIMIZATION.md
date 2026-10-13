# 推理优化与训练数据诊断

负责人 A；2026-10-13。目标仍是原始八类正确检测在同一个全局置信度下，Precision 和 Recall 都超过 70%。本轮先验证现有权重的推理方法，新增训练 0 次、下载权重 0 次、升级依赖 0 次。业务接口、人工审核策略和运行中的后端不变。

## 运行前冻结的比较

[计划](../SystemCode/experiments/vision/inference_followup_plan.json)与[协议补充](../SystemCode/experiments/vision/inference_followup_clarifications.json)在实验前固定了八个候选、预算、输入哈希及选择规则。全部使用已有的 1,921 张验证原图和 2,623 个标注框；这些验证数据已参与开发，不能当成新的独立测试。

| 候选 | 方法 | 要验证的问题 |
| --- | --- | --- |
| baseline832 | 当前 best，832，全图 | 已有基线：P 50.52%、R 52.00% |
| renms832 | 对缓存结果再做同类 NMS 0.5 | 减少重复框是否能改善正确比例 |
| standard640 | 当前 best，全图640 | 更低分辨率是否适合本数据尺度 |
| standard960 | 当前 best，全图960 | 增大分辨率能否减少漏检 |
| flip832 | 原图与水平翻转，共2视图 | 不同视角的候选能否互补 |
| tiles832 | 全图与4个重叠角落切片，共5视图 | 放大小损坏能否改善召回 |
| ensemble_union | 父模型640与当前模型832候选合并 | 两个检查点的错误能否互补 |
| ensemble_paired | 两模型同类配对、重新评分 | 一致检测能否改善分数排序 |

所有新增视图使用 FP32、batch1、GPU0，置信度下限0.001、视图内同类 NMS0.7、每视图最多100框。融合后最多100框；standard候选保留原始视图结果，其余方法使用同类NMS0.5。切片宽高分别为原图的0.625向上取整，坐标恢复到原图；全图仍保留。新增总预算为17,289次图像视图推理。

配对法不是标准 WBF 实现：两模型同类框按固定贪心顺序，以IoU≥0.55一对一配对，坐标按置信度加权。配对分数是两分数平均；单模型框的分数减半。低于0.001的结果丢弃。它是待验证的排序启发式，不能解释为校准后的正确概率。两个权重具有父子微调关系，也不是独立投票。

缓存候选已受NMS0.7及top100截断影响，再做NMS0.5不等价于重新运行检测器的NMS0.5。翻转与切片使用本项目明确实现，未安装SAHI，也没有声称复现库内多尺度TTA。

## 指标与选择

主指标保持八类同类一对一IoU≥0.5匹配。IoU≥0.3只诊断框偏移，不用于替换主指标或挑选模型。每种方法使用相同的25个阈值，按 `min(micro P, micro R)` 最大、再按macro F1、再按micro R选择操作点，平局使用较早阈值或候选。

同时报告全局最高分候选和可推荐候选。可推荐候选须在自己的选中操作点，相对基线的P与R**都严格提高**；若没有则保留基线。报告每类支持数与退步，不能用总体改善掩盖稀有类别下降。复合推理方法输出实验配方，不能直接伪装成仅支持单权重的`roadguard-model-v1`清单。

逐图结果采用原子写入，可通过`--resume`恢复；恢复必须保持权重、数据、源码、运行环境和设置身份一致。所有大体积证据放在忽略上传的`Dataset/inference-followup/`。原训练best/last和完整恢复检查点保留。

## 数据与损失诊断

本轮只定向检查20张训练原图：宽纵裂、宽横裂、下陷龟裂、深坑各4张，加4张空标注图片。局部审查不代表全库标注质量，也没有修改标签。样本ID、原图与标注SHA256、原始框和联系表保存于`Dataset/inference-followup/data-audit/`。

- 原始训练图8,958张，空标注2,865张（32.0%）；镜像相同数量。镜像增加训练次数，不增加独立场景。宽横裂、下陷龟裂、深坑原始框只有243、311、193个。
- 两张空标注训练图可见裂纹样接缝或纹理；是否属于应标损坏，需结合源标注规范人工判断。不能把所有空标注图片直接作为可靠的困难负样本。
- 训练元数据出现16对同family不同亚类框IoU≥0.9，属于复核候选；重叠本身不足以确认错标。单张RGB照片也不能独立确认工程深度。
- 已安装Ultralytics8.4.176的类别权重乘在BCE正负项上，不只增加稀有正例权重。实际未安装Albumentations，不声称使用其默认增强。
- 上轮epoch10至40，训练分类loss由1.661降至0.939，验证分类loss由2.214升至2.481，原生mAP50–95由0.203降至0.182。它与泛化差距一致，但增强也有变化，不是单一参数的因果证明；不支持盲目续加训练轮数。

当前best在confidence0.05已有八类Recall72.05%，Precision却只有23.68%（TP1890、FP6090）。在这个固定候选池内达到双70%，至少保留1,837个TP，同时把FP降至787以下：需要保留至少97.2%的现有TP并过滤至少87.1%的FP。该算术说明目标难度，并不预测某种新方法能做到。

若本轮推理改善仍有限，下一项值得验证的是“损坏/背景拒绝＋原八类”的候选框二阶段复核模型，使用训练集内的损坏裁剪和人工筛过的困难负样本。普通八分类器会被迫给背景分配损坏类别，无法单独解决误报。新训练应另行冻结小规模预算、保留源图分组与镜像关联，并评估完整两阶段流程；不能把验证误报直接回填训练或未经审查自动重标。

## 方法依据

[Ultralytics切片推理说明](https://docs.ultralytics.com/guides/sahi-tiled-inference/)与[SAHI切片指南](https://obss.github.io/sahi/guides/sliced-inference/)说明通过切片放大小目标并合并结果的思路；本项目采用固定四角切片。

[Ultralytics TTA说明](https://docs.ultralytics.com/yolov5/tutorials/test-time-augmentation/)说明测试时多视图预测的思路；这里仅比较明确的原图与水平翻转两视图，不复现该文YOLOv5实现。[Weighted Boxes Fusion论文](https://arxiv.org/abs/1910.13302)提供多模型框融合参考；本轮配对法的规则以冻结协议为准，不复用论文名称作为效果保证。

## 运行结果

八候选均已完成全部验证原图与固定25点阈值比较。主指标没有任何候选在网格内达到双70%；八类均未同时达到P/R70%。结果如下（百分比）：

| 候选 | confidence | TP / FP / FN | P | R | F1 | macro F1 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| baseline832 | 0.25 | 1364 / 1336 / 1259 | 50.52 | 52.00 | 51.25 | 42.62 |
| renms832 | 0.25 | 1347 / 1159 / 1276 | 53.75 | 51.35 | 52.52 | 43.30 |
| standard640 | 0.25 | 1279 / 1273 / 1344 | 50.12 | 48.76 | 49.43 | 39.54 |
| standard960 | 0.25 | 1331 / 1378 / 1292 | 49.13 | 50.74 | 49.92 | 42.00 |
| flip832 | 0.3 | 1397 / 1238 / 1226 | 53.02 | 53.26 | 53.14 | 43.08 |
| tiles832 | 0.35 | 1271 / 1404 / 1352 | 47.51 | 48.46 | 47.98 | 38.70 |
| ensemble_union | 0.3 | 1408 / 1321 / 1215 | 51.59 | 53.68 | 52.62 | 43.70 |
| ensemble_paired | 0.2 | 1446 / 1362 / 1177 | 51.50 | 55.13 | 53.25 | 44.09 |

全局最高分与严格双指标改善的候选均为 **flip832，confidence0.30**。相对基线P提高2.50个百分点、R提高1.26个百分点，增加33TP、减少98FP与33FN。Macro P/R/F1为43.24%/43.46%/43.08%；macro Recall略低于基线43.52%，仍不能称作各类全面改善。配对融合在选中点召回55.13%更高，但Precision为51.50%，按事先均衡规则没有胜出。

| ID / 类别 | support | 基线 P / R / F1 | flip832 P / R / F1 |
| --- | ---: | --- | --- |
| 0 longitudinal crack | 941 | 57.66 / 60.79 / 59.18 | 60.51 / 63.02 / 61.74 |
| 1 longitudinal crack wide | 148 | 38.07 / 45.27 / 41.36 | 38.17 / 47.97 / 42.51 |
| 2 transverse crack | 541 | 50.28 / 49.54 / 49.91 | 53.23 / 50.28 / 51.71 |
| 3 transverse crack wide | 46 | 36.84 / 30.43 / 33.33 | 36.36 / 26.09 / 30.38 |
| 4 alligator crack | 526 | 57.89 / 54.37 / 56.08 | 62.86 / 54.37 / 58.31 |
| 5 alligator crack sunken | 77 | 24.49 / 31.17 / 27.43 | 28.21 / 28.57 / 28.39 |
| 6 pothole | 299 | 36.25 / 38.80 / 37.48 | 36.98 / 41.81 / 39.25 |
| 7 pothole deep | 45 | 34.69 / 37.78 / 36.17 | 29.63 / 35.56 / 32.32 |

宽横裂、下陷龟裂、深坑的Recall下降；宽横裂和深坑F1也下降。更高的总体分数仍受到大类支持数量影响。IoU0.3只作为辅助诊断保留在JSON，不改变这项结论。

## CPU与外部图片验收

在同样40张按国家平衡的固定验证原图上，各2次预热、3轮共120次测量，4个CPU线程、1个interop线程、FP32：基线中位数 **85.19 ms**、P95 **99.00 ms**；flip832中位数 **142.64 ms**、P95 **160.94 ms**，中位耗时约为基线 **1.67倍**。

计时包括ImageStore.prepare、归一化PNG解码、完整视图/融合与阈值过滤，排除权重加载、磁盘读取、DTO与HTTP/数据库。它是实验配方的CPU检查，尚未接入真实API。首轮计时与六图CPU推理有重叠，保留但不用于报告；正式耗时来自无其他本次模型推理并行的`acceptance-isolated-v2`。

40图归一化前后RGB像素一致。两候选各25图CPU/GPU输出有数值差异、各23图超出严格IoU0.99/分数1e-4容差；按同类IoU0.5匹配，flip输出全部对应，基线少1个GPU候选。CPU重复输出一致性及最大数值差异见摘要。不能把GPU的完整验证指标直接当作已经复测的CPU全量准确率。

已有六张真实外部图片在选择完成后复测，无新增挑图或调参。龟裂图片仍能检出；一张路面照片新增右侧裂纹区域，但“下陷”仍未经工程确认；明显坑洞近照仍漏检，减速带边缘误报仍存在。选择点0.30还过滤掉原来低于0.30的真实坑洞候选。该结果不足以支持实际业务自动放行，六图也没有专家GT，不能计算准确率。原结果、来源/许可和新的逐图对照均保留于`Dataset/inference-followup/external-selected/`。

## 工程验收与交付边界

- 新工具与原指标工具相关测试64通过；完整回归790通过、1项Windows符号链接权限测试跳过；CI guard 44通过。首次默认临时目录/沙箱TestClient受限，最终使用工作区临时目录完成完整检查。
- 独立审阅修正并验证了中断缓存完整性检查和融合最终分数平局的来源顺序；主agent实际检查5张训练审查联系表和6张外部对照图。
- 推理源码提交`173d0e1`，SHA256 `e6856697cd5a6bfd816a860b85441b5563f23a55887e4142d1454d11fcb3833f`；两种standard分辨率复用未修改的balanced_metrics.py导出器。
- 所有输入/模型/协议及完整逐图结果身份均经校验；没有打开test图片或标注用于本轮选择，没有改标签、依赖、业务接口、workflow或PyCharm配置。
- 全部训练检查点继续保留。本轮没有新训练，也没有生成可清理的train.cache/val.cache；预测证据不作为多余缓存删除，Dataset继续整体Git忽略。

该实验配方可用于后续验证；**没有替换运行中的模型**。考虑只有小幅增益、CPU成本增加、稀有类退步及真实坑洞漏检，下一轮优先做标签与困难负样本核验，再设计带背景拒绝的二阶段复核小实验。不能承诺这样就达到双70%，也不继续无边界尝试更多阈值或训练轮次。

可分享证据：[完整摘要](../SystemCode/experiments/vision/inference_followup_summary.json)、[操作点CSV](../SystemCode/experiments/vision/inference_followup_operating_points.csv)、[指标图](../SystemCode/experiments/vision/inference_followup_operating_points.png)、[逐类F1](../SystemCode/experiments/vision/inference_followup_per_class.png)、[数据诊断](../SystemCode/experiments/vision/inference_followup_data_diagnosis.json)。

## 复现命令

从仓库根目录运行；需要本机已有相同权重、数据与冻结计划。standard640/960本轮使用原导出器；下列命令只展示模式，已存在输出应使用恢复参数或新名称，不能覆盖证据。

```powershell
.venv/Scripts/python.exe SystemCode/model/balanced_metrics.py export --weights Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/weights/best.pt --run-name inference-followup-standard640 --imgsz 640 --device 0
.venv/Scripts/python.exe SystemCode/model/inference_experiments.py export --weights Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/weights/best.pt --run-name flip832 --method flip --imgsz 832 --nms-iou 0.5 --device 0
.venv/Scripts/python.exe SystemCode/model/inference_experiments.py analyze --export Dataset/inference-followup/flip832/export.json
```

切片使用`--method tiles`；缓存融合使用`fuse --exports ... --strategy union_nms|paired_score --run-name ...`。`compare --exports ... --run-name ...`要求冻结的八候选顺序：baseline832、renms832、standard640、standard960、flip832、tiles832、ensemble_union、ensemble_paired。只有新工具支持逐图`--resume`；原导出器拒绝重复输出。CPU与外部图片检查由本机任务脚本完成，报告保留脚本哈希与完整计时边界，不声称这些临时脚本随Git发布。
