# Precision / Recall 均衡优化实验

日期：2026-10-13；负责人 A。**本轮未达到 Precision / Recall 同时 70% 的目标。** 冻结选择规则选出 `new_best832`、全局 confidence 0.25：八类同类 IoU≥0.5 的 micro Precision **50.52%**、Recall **52.00%**、F1 **51.25%**。相对父模型 best@640 的 48.62% / 51.20% / 49.88%，分别增加 **1.89 / 0.80 / 1.37 个百分点**，属于小幅验证集增益；没有任何一个类别同时达到双 70%。

用户要求尽量少漏检并正确区分八类损坏，定位框细微偏移可以次要处理。下面保留运行前冻结的预算、参数与排序口径，再记录实际结果和工程验收；数值／恢复／HTTP 检查通过不等于识别目标达到或可自动接受真实巡检。

## 目标与口径

主要目标是在同一个全局置信度阈值下，**八类、同类一对一匹配、IoU≥0.5 的 micro Precision 和 Recall 均≥70%**。每类 support、Precision、Recall、F1 和 macro 均值必须同时报告；总体达到目标也不表示每个少数类都达标。

额外报告 IoU≥0.3 的宽松定位诊断，以及不区分类别／合并四大类的诊断，用于辨别框偏移与类型混淆。它们不能替代主要八类结果，不能通过合并标签、忽略误报或降低匹配标准宣称达到主要目标。框位置不是第一优先级，因此本轮选择标准从上一轮的 mAP50–95 调整为均衡 Precision / Recall；标准 mAP 仍作为辅助证据保留。

Precision、Recall 和定位 IoU 是不同维度；F1 可概括二者的平衡，但仅高 F1 也不保证 Precision 与 Recall 各自超过 70%。概念依据见 [Ultralytics 指标说明](https://docs.ultralytics.com/guides/yolo-performance-metrics)。

## 第一轮预算与固定训练配置

只安排一组全量微调实验，**额外 40 轮，832 像素，batch 16**；另有 64 张训练／32 张验证图的两轮中断恢复检查，只验证运行机制，不作模型效果证据。本轮无包升级、无新权重下载；模型从已有 s30 best.pt 初始化，使用新的运行名和优化器，旧实验完整保留。

冻结机器可读计划：[balanced70_plan.json](../SystemCode/experiments/vision/balanced70_plan.json)。本地配置为 `Dataset/balanced70/s40-config.json`，运行名 `yolo11s-rdd2022es-balanced40-img832-seed42`。

| 设置 | 固定值 / 原因 |
| --- | --- |
| 初始化 | 上一轮 s30 best.pt；SHA256 `92749da1b1c05f2186e388c9d0cee65cc868613662c5aa21d940d76ec003940a` |
| 数据 | 同一冻结 train / val；八类 ID 不变，不打开 test 图片或标注 |
| 运行 | 40 epoch、patience 40、imgsz 832、batch 16、nbs 64、seed 42、workers 4 |
| 优化器 | AdamW，lr0 0.0002、lrf 0.1、warmup 1 轮、warmup_bias_lr 0 |
| 分类 | cls 0.75、cls_pw 0.25；适度增加分类损失和少数类权重 |
| 定位损失 | box 7.5、dfl 1.5；保留检测学习所需的定位损失 |
| 增强 | mosaic 0.5，最后 10 轮关闭；scale 0.3、translate 0.05、hsv_s 0.4、hsv_v 0.3 |
| 其余 | amp false、cache false、deterministic true、fliplr 0；不加旋转、纵向翻转、mixup、cutmix、copy_paste |

安装的 Ultralytics 8.4.176 原生支持 `cls_pw`：从训练标注数量计算逆频率的指定幂并归一化，分类 BCE 的正负项都会受影响。这不是“复制少数类后一定更准”的保证；需要检查它是否增加少数类误报。训练样本含源镜像，稀有框数量不等于独立拍摄实例数量。官方扩展说明见 [Customizing Trainer](https://docs.ultralytics.com/guides/custom-trainer)，本轮具体 API 以锁定安装版本源码为准。

多数原始图片宽高尺度为 600～720 像素，832 可能改变特征采样，但不会凭空恢复图片细节。本轮同时改变分辨率、学习率、增强和分类权重，属于有目的的优化尝试，不能将结果归因于其中单一参数。微调含义见 [官方训练建议](https://docs.ultralytics.com/guides/model-training-tips)。

## 阈值与模型选择

候选顺序固定为：父模型 best@640、父模型 best@832、新模型 best@832、新模型 last@832。父模型双分辨率分析用于区分单纯改变推理分辨率与新训练的结果。新 best.pt 仍由库的 mAP50–95 选出；另外检查 last.pt，避免只观察偏重精确定位的检查点。未声称穷举每轮的最佳均衡检查点。

对每个候选，在全部 1,921 张验证原图上单图推理一次，导出 conf=0.001、NMS IoU=0.7、max_det=100、FP32 的原始结果。随后离线扫描冻结计划中的 25 个阈值，阈值选择按：

1. 最大化八类 IoU 0.5 的 `min(micro Precision, micro Recall)`。
2. 相同时，取八类 macro F1 较高者，再取 micro Recall 较高者。
3. 完全相同时，阈值保留列表中较早者；模型保留候选列表中较早者。

主要阈值适用于全部八类，不按少数几个好看的案例设不同阈值。IoU 0.3、四大类或不分类诊断不能参与主要排序。每个候选的完整曲线及逐类结果都保留，失败实验也记录。

本次按上述协议使用验证集选阈值与模型；验证集过去也已参与训练和选型，因此结果称为“验证集调优结果”，不能称为新的独立泛化证明。历史 test 已在初始基线中被查看，本轮未打开 test 图片或标签，也未对候选运行 test 评估。

## 验收与存储

- 主 agent 复核新增工具及配置，运行适用测试；GPT-6.1-sol 子 agent 开发，职责和证据写入最终验收。
- 先完成高分辨率、类别加权设置的真实中断恢复小样本检查，再进行冻结的全量训练。
- 每轮保存完整恢复状态；保留 best、last、resume-latest、resume-previous 及配置、日志、来源哈希。
- 对最终候选复核权重与输入身份、有限张量、样本错误及真实 HTTP 业务连接。所有真实非空检测仍需人工审核，业务规则保持演示状态。
- 验证通过后仅清理已列明的可重建缓存，不删除模型、原始数据或评估证据。
- `Dataset/` 整体忽略，不上传 GitHub；Git 只保留工具、文档、配置与小型统计汇总。PR 内容保持英文并遵循现有自动 CI／合并流程。

如果本轮没有达到“双 70%”，必须如实记录最佳结果及仍然限制效果的原因，不通过改名指标或只报告 Precision 的方式宣布成功。

## 实际训练与四候选结果

新增全量训练按冻结配置完成 40 轮，日志耗时 **4,762.9 秒（约 79.4 分钟）**，唯一随机种子 42。训练源码为干净提交 `bec6fb33d594544d00d06cbfb4ffeb74722cd138`；运行及冻结源码哈希经完整性核对一致。实际 batch 16、nbs 64、nominal accumulate 4，名义有效 batch 64；最终 epoch=40。新 best 对应本轮 **第 10 轮**的库内 mAP50–95 最优点，last 对应第 40 轮。本轮只比较 best 和 last，并未导出每轮权重寻找最优均衡点。

计划中的 `config_sha256` 是配置文件原始字节摘要 `e73285b0b37ba1668da2ce12dc8a718d302df1de53cb700cbe2bcb17cde4a010`；训练身份的配置指纹为规范化 JSON 摘要 `0840d4e41a7babc51119b3da9a06414667e7ed93a009660039380078796f8695`。二者口径不同，均已分别核对。

下表均为全部 1,921 张验证原图、2,623 个标注框的八类同类 IoU≥0.5 结果；每个候选按冻结网格选择一个适用于所有类别的 confidence。表内 P/R/F1 为百分比。

| 候选 | 分辨率 | confidence | TP / FP / FN | micro P | micro R | micro F1 | macro F1 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| parent_best640 | 640 | 0.25 | 1343 / 1419 / 1280 | 48.62 | 51.20 | 49.88 | 40.92 |
| parent_best832 | 832 | 0.25 | 1241 / 1222 / 1382 | 50.39 | 47.31 | 48.80 | 37.67 |
| **new_best832（选中）** | **832** | **0.25** | **1364 / 1336 / 1259** | **50.52** | **52.00** | **51.25** | **42.62** |
| new_last832 | 832 | 0.35 | 1318 / 1254 / 1305 | 51.24 | 50.25 | 50.74 | 42.00 |

四候选的冻结 25 点网格均没有同时达到主 micro 双 70%。last 的 Precision 略高，但 `min(P,R)` 低于 best，故按事先规则选择 best。相对父模型640，选中模型增加21个TP、减少83个FP、减少21个FN；仅把父模型推理分辨率改832反而降低Recall，不能把新模型结果归因于分辨率本身。

选中点的八类等权 macro P/R/F1 为 **42.02% / 43.52% / 42.62%**；父模型640为 **40.71% / 41.93% / 40.92%**。Macro 不按类别数量加权；undefined项平均时贡献0，逐类原值保留null。本轮八类均有GT。

## 八类支持数与父模型对比

下表保持原始0～7类别，所有P/R/F1仍使用同一个confidence0.25和主IoU0.5。`support`是验证标注框数量，不是独立照片数；P/R/F1三元组为百分比。

| ID / 源类别 | support | 父模型640 P / R / F1 | 选中模型832 P / R / F1 |
| --- | ---: | --- | --- |
| 0 longitudinal crack | 941 | 51.67 / 61.00 / 55.95 | 57.66 / 60.79 / 59.18 |
| 1 longitudinal crack wide | 148 | 34.34 / 45.95 / 39.31 | 38.07 / 45.27 / 41.36 |
| 2 transverse crack | 541 | 49.29 / 51.39 / 50.32 | 50.28 / 49.54 / 49.91 |
| 3 transverse crack wide | 46 | 24.14 / 15.22 / 18.67 | 36.84 / 30.43 / 33.33 |
| 4 alligator crack | 526 | 56.93 / 51.52 / 54.09 | 57.89 / 54.37 / 56.08 |
| 5 alligator crack sunken | 77 | 36.99 / 35.06 / 36.00 | **24.49 / 31.17 / 27.43** |
| 6 pothole | 299 | 38.98 / 33.11 / 35.80 | 36.25 / 38.80 / 37.48 |
| 7 pothole deep | 45 | 33.33 / 42.22 / 37.25 | 34.69 / 37.78 / 36.17 |

宽横裂的F1有所提高，但下陷龟裂的Precision、Recall和F1全部下降，FP由46增至74、TP由27降至24。横裂和深坑的F1也下降；因此不能称作“八类全面提升”，也不能把类别加权视为已证明有效的单独原因。

## 辅助定位诊断与原生mAP

下面只对选中权重与同一confidence0.25作诊断，不重新选阈值、不替换主指标。

| 匹配诊断 | micro P | micro R | micro F1 |
| --- | ---: | ---: | ---: |
| **八类同类 IoU≥0.5（主指标）** | **50.52** | **52.00** | **51.25** |
| 八类同类 IoU≥0.3 | 55.48 | 57.11 | 56.28 |
| 四个family IoU≥0.5，仅诊断 | 54.41 | 56.00 | 55.19 |
| 不分类 IoU≥0.5，仅定位诊断 | 55.67 | 57.30 | 56.47 |
| 不分类 IoU≥0.3，仅定位诊断 | 61.78 | 63.59 | 62.67 |

即使忽略类别并放宽到IoU0.3，该操作点也未达到双70%，不能把框偏移当作全部差距。不同贪心匹配可能有不同配对，表中增量不能当作互斥因果贡献相加；八类名称与接口始终保留。

另一次原生Ultralytics验证保存为 `Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/evaluation-val.json`：选中best的 **mAP50=40.16%、mAP50–95=20.27%**；父模型原生结果为38.77%、20.23%。原生P/R/F1在库的最大平均F1曲线位置计算，收集conf=0.001、NMS IoU=0.7，并非上表confidence0.25的micro计数。mAP也不是照片分类正确率，不能混写为“双70%准确率”。

## 错误、数据支持与探索案例

选中点的1,259个FN按明确优先顺序互斥归类：missed **896（71.2%）**、localization220、confusion143；1,336个FP分为background628、localization340、confusion264、duplicate104。FP与FN是两个单独分区，同一个错类/偏移对象可能各产生一个FP和FN，不能把两边相加当成独立物理缺陷数。Missed是该操作点未建立诊断匹配，不等于图像没有更低confidence候选。Background也不能直接证明漏标。

不分类IoU0.5匹配中的错八类配对有190个：同family亚类146、不同family44，说明普通/宽、普通/下陷、普通/深等亚类混淆仍存在。40张定向分层对照与完整逐图证据保存于 `Dataset/balanced70/selected-errors/report.json`，并非随机质量估计。

冻结train有8,958张原图和8,958张镜像，有效框数被镜像翻倍。八类原始训练框数依次为 **4556、820、2614、243、2443、311、1477、193**；验证框数见上表。宽横裂、下陷龟裂、深坑的原始支持group数只有230、288、157，存在明显不平衡，不能把镜像当作新增独立场景。现有观察只能提示稀有支持与类别歧义可能限制效果，不能证明训练数据数量足够或不足。

选中点的GT面积小于图像1%时Recall为424/934=45.4%，面积≥20%时为81/108=75.0%；FN框原图短边中位数48像素，TP约59.5像素，missed分区约43像素。它们是图像空间几何，不是工程损坏尺寸；没有冻结contrast字段，本轮未测量contrast，未据此下结论。按国家的P/R分别为Czech43.33%/34.32%、India42.86%/37.40%、Japan48.59%/48.48%、United States55.35%/65.38%，同样不代表Jurong影像表现。

三张运行前确定的验证原图保留GT/父模型/选中模型对照：`India_001650`的2个FN仍未检出；`Japan_003097`从0TP/1FP/1FN变为1TP/0FP/0FN；`Japan_005511`从3TP/5FP/3FN变为2TP/4FP/4FN。这些 本地探索案例（`Dataset/balanced70/selected-errors/illustrative/`）同时展示改善、未改善和退步，不能用于代表整体准确率，也未确认标注错误或修改标签。

本轮多个训练参数同时改变，仅一个seed，没有消融、重复种子或置信区间。小增益不能归因于单个参数，不能声称统计显著或新场景泛化。下一步应先开展可复核的数据/标签审查与稀有亚类支持工作，尤其普通/宽、下陷和深坑的定义与一致性；保留八类，建立审核证据后再决定下一组有预算的实验，避免直接追加盲目epoch。

## 已完成工程验收与后续使用

- 全量前已用832、类别加权配置完成真实两轮中断恢复小样本检查；它只验证机制，不提供全量准确率。
- 全量40轮及运行实参核验完成；latest/previous分别保存epoch40/39、255项optimizer state，live/EMA张量与best/last各499个张量finite，类别权重与冻结公式匹配。
- 完整性检查核对train/val **39,674个图片/标签文件SHA256**，与冻结manifest一致；train/val/test group元数据不相交。为了核对隔离读取test元数据，但未打开其图片/标签，未创建候选test评估。
- 普通回归 **761 passed、1 skipped**；CI guard **44 passed**。数值范围、标签、样本与身份检查通过，均不等于双70%目标通过。
- 选中清单完成隔离loopback Uvicorn真实HTTP **11个响应案例**：上传、请求重放、审核与审核重放、活动/完成任务快照、任务完成、服务重启后持久数据、禁用真实检测后新请求503。输入revision为0→1→2；默认8000端口未使用。
- 真实Detection为`is_demo=false`并仍强制先人工审核；HTTP自动审核仅验业务连接，坐标是模拟Jurong坐标、任务业务规则仍为demo，不是专家或生产验收。
- 主agent实际查看两张指标图、覆盖40张分层案例的四张contact sheet，以及三张固定案例的完整对照。该检查核对证据展示与探索错误，不构成专家标注确认；没有修正任何标签。

本地推荐清单为 `Dataset/balanced70/selected_model_manifest.json`，权重SHA256 `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`，confidence0.25、NMS IoU0.7、imgsz832，状态保持experimental。本轮只生成推荐并做隔离验收，**未修改现有PyCharm启动配置、环境变量或运行中的后端**。需要使用时按 [真实视觉API说明](REAL_VISION_API.md)显式配置 `ROADGUARD_VISION_MANIFEST_PATH`；不会自动激活。

可分享的小型证据为 [summary](../SystemCode/experiments/vision/balanced70_summary.json)、[四候选操作点CSV](../SystemCode/experiments/vision/balanced70_operating_points.csv)、[40轮训练CSV](../SystemCode/experiments/vision/balanced70_training_results.csv)、[PR曲线](../SystemCode/experiments/vision/balanced70_pr_curves.png)、[逐类对比图](../SystemCode/experiments/vision/balanced70_per_class.png)。本地完整证据在 `Dataset/balanced70/selection.json`、`integrity.json`、`selected-errors/`、`http-acceptance/`、`data-diagnostics/`与实际run目录；它们保持Git忽略。

数值、完整性、HTTP、错误与视觉检查完成后，已实际应用白名单清理：本地 `Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/cleanup-applied.json`记录仅删除 `prepared/labels/train.cache` **4,344,707字节**与 `val.cache` **452,896字节**，合计 **4,797,603字节（约4.80 MB / 4.58 MiB）**。原始数据、划分、预测、报告及全部旧/新best、last、resume-latest、resume-previous检查点保留；没有清除测试图片/标签或模型证据。
