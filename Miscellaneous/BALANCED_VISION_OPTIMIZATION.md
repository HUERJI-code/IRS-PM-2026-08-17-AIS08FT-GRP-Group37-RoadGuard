# Precision / Recall 均衡优化实验

日期：2026-10-13；负责人 A。用户明确希望 Precision 与 Recall 都争取超过 70%，尽量少漏检并正确区分八类损坏，定位框的细微偏移可以次要处理。本文先冻结本轮协议，实际结果在运行结束后追加；参数本身不代表目标已达到。

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

这次会使用验证集选阈值与模型；验证集过去也已参与训练和选型，因此结果必须称为“验证集调优结果”，不能称为新的独立泛化证明。历史 test 已在初始基线中被查看，本轮不继续用它调参或反复评估。

## 验收与存储

- 主 agent 复核新增工具及配置，运行适用测试；GPT-6.1-sol 子 agent 开发，职责和证据写入最终验收。
- 先完成高分辨率、类别加权设置的真实中断恢复小样本检查，再进行冻结的全量训练。
- 每轮保存完整恢复状态；保留 best、last、resume-latest、resume-previous 及配置、日志、来源哈希。
- 对最终候选复核权重与输入身份、有限张量、样本错误及真实 HTTP 业务连接。所有真实非空检测仍需人工审核，业务规则保持演示状态。
- 验证通过后仅清理已列明的可重建缓存，不删除模型、原始数据或评估证据。
- `Dataset/` 整体忽略，不上传 GitHub；Git 只保留工具、文档、配置与小型统计汇总。PR 内容保持英文并遵循现有自动 CI／合并流程。

如果本轮没有达到“双 70%”，必须如实记录最佳结果及仍然限制效果的原因，不通过改名指标或只报告 Precision 的方式宣布成功。
