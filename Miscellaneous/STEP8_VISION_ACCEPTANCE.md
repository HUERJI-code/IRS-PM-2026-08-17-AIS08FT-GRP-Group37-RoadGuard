# 第 8 步视觉模型实施与验收记录

日期：2026-10-13；负责人：A；开发由 GPT-6.1-sol 子 agent 分工完成，主 agent 独立验收。

## 当前边界

本步已完成全量数据准备、可恢复训练/评估、真实检测接入，并实际跑通 10 epoch GPU 基线与真实 HTTP 验收。功能验收通过，模型保持 `experimental`；数值有效性不代表已达到生产准确率。业务规则仍为演示假设，真实非空检测一律进入人工审核。B 的路线、C 的前端/助手和跨模块联调不属于本步完成项。

## 数据与硬件

- 数据固定为 `juusos/rdd2022es` 第 1 版；不是 Jurong 实拍数据。
- 完整 ZIP：2,611,933,018 字节；SHA-256：`3ceb9de3b7ca7083379e4fc62748bafcda0a82d1baf4627cf87891c9595fa775`。
- 所有大文件保存在仓库根目录 `Dataset/`，该目录整体被 `.gitignore` 排除。原始数据、划分、模型、数据库、日志不上传 GitHub；仓库保留实现、测试、配置示例和小型统计证据。
- 已验证本机 RTX 5090、32 GB 显存、CUDA 12.8 / PyTorch 2.10.0 GPU 运算。YOLO 库固定 Ultralytics 8.4.176；官方初始权重为 YOLO11n COCO 预训练模型，不能直接当作八类道路模型。
- 第一次逐张检查完成 25,600 张图片，发现 `India_000430`（EXIF 8）和 `India_004098`（EXIF 3）。两组原图/镜像按确切哈希核验后隔离，未修改原图或猜测旋转标签；首次失败报告保存在 `Dataset/audits/initial-exif-failure/`。
- 既有缺标注 `Czech_001003` 原图/镜像和孤立 `India_001032.txt` 同样隔离；详细处理见[数据流水线说明](../SystemCode/model/data_readme.md)。

第二次全量检查完成，25,600 张图片逐张完整解码、标注/坐标/镜像关系校验通过，文档指定的三组问题原图及镜像隔离；未发现其他待处理错误。按原图/镜像、相同内容和保守近似重复关系分组，额外连接 26 对近似组；seed 42，按国家分层后按组约 70/15/15 划分，三个集合的 group ID 无交集。近似检查不能保证发现全部相邻场景，缺少拍摄序列/GPS，不能声称完全无场景泄漏。

| 集合 | 图片 | 组 | 标注框 | 用途 |
| --- | ---: | ---: | ---: | --- |
| train | 17,916 | 8,939 | 25,314 | 含 8,958 原图及对应镜像 |
| val | 1,921 | 1,917 | 2,623 | 仅原图，用于训练选优 |
| test | 1,918 | 1,915 | 2,673 | 仅原图，固定模型后评估 |

准备文件通过 43,510 个硬链接复用原始图片/标签，避免另占一份空间。训练完成后再次核对全 manifest 25,600 行的原图/标注 SHA-256，内容未变化，准备文件仍指向原始内容，组间无交集。原始审计及划分证据位于 `Dataset/prepared/`。

## 实际训练与指标

运行：`Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/`。YOLO11n 从官方 COCO 权重迁移训练为八类；10 epoch、640 像素、batch 32、seed 42、AdamW、lr0 0.001、lrf 0.01、warmup 1、workers 4、amp=false、cache=false、fliplr=0。`results.csv` 的 epoch 累计用时约 496.9 秒，不包括下载/准备、单独评估和验收。30 epoch 配置示例没有在本次运行。

固定最佳权重后，分别评估 1,921 张验证图和 1,918 张测试图；499 个模型参数/缓冲张量均为有限值，八类名称及顺序一致。实际结果如下（百分比）：

| 集合 | Precision | Recall | 宏平均 F1 | mAP@50 | mAP@50–95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| val | 35.04 | 42.94 | 37.61 | 34.28 | 16.93 |
| test | 39.15 | 41.21 | 38.56 | 36.19 | 18.38 |

| 类别 | val 框数 | val AP@50 | test 框数 | test AP@50 |
| --- | ---: | ---: | ---: | ---: |
| longitudinal crack | 941 | 54.93 | 908 | 51.67 |
| longitudinal crack wide | 148 | 29.63 | 202 | 41.29 |
| transverse crack | 541 | 44.67 | 573 | 46.48 |
| transverse crack wide | 46 | 17.67 | 65 | 24.00 |
| alligator crack | 526 | 50.66 | 488 | 44.67 |
| alligator crack sunken | 77 | 23.36 | 65 | 29.69 |
| pothole | 299 | 26.74 | 336 | 26.46 |
| pothole deep | 45 | 26.57 | 36 | 25.23 |

这是初始实验基线，稀少类别及坑洞检测仍弱。mAP 是检测平均精度，不能解释成“正确识别图片的比例”。P/R/F1 来自各自曲线的最大平均 F1 描述点，没有使用测试集选择模型、训练参数或部署阈值。评估保留 conf=0.001 的预测以计算曲线；混淆矩阵也按此阈值生成，不能拿背景误报数量直接表示后端 conf=0.25 的误报数。后端的 0.25 只是返回预测的过滤参数，尚未校准为自动接受阈值。

上述指标来自固定版本 Ultralytics 原生八类评估。可选 `faster-coco-eval` 未安装，日志明确警告；不宣称另一个 COCO 评估器已运行。全部原始报告、每类指标、PR 曲线、混淆矩阵、预测 JSON 和可视化留在运行目录。小型可提交证据见[实验摘要](../SystemCode/experiments/vision/step8_baseline_summary.json)和[逐轮结果](../SystemCode/experiments/vision/baseline10_results.csv)。

最佳权重 SHA-256：`6701105881507946244e27d4155fa9febc2ad0bd2657bf52ee519a824c1619de`。训练时工作区尚未提交；`run_metadata.json` 保留当时 HEAD、dirty 标志和源文件哈希。训练后补强 Dataset/YAML 路径校验，未改变实际模型、优化器、数据、配置或评估器；不能把记录的 base HEAD 当作完整训练代码版本。

## 保存点与恢复

每个完成的 epoch 原子保存 `resume-latest.pt`，另保留 `resume-previous.pt`；包括实时模型、EMA、优化器、学习率调度器、随机状态等。`best.pt` 和 `last.pt` 分别保存最佳与最终模型，恢复检查点独立保留完整状态。中断会丢失正在进行的这一轮；下一次从最近完成的轮次继续。

实际恢复验收通过：独立 smoke 使用固定训练/验证子集 64/32 张、2 epoch；第 1 轮持久保存后主动中断，再显式指定 `resume-latest.pt` 启动，从第 2 轮继续，`resume_verified.json` 记录 start_epoch=1（从零计数）、optimizer_state_entries=255。随后验证成功，生成八类模型清单。smoke 的模型质量不计入上述正式基线结果。

正式运行另有第 10 轮 `resume-latest.pt`、第 9 轮 `resume-previous.pt`，以及最佳 `best.pt`、最终 `last.pt`。命令、损坏回退及配置一致性约束见[训练说明](../SystemCode/model/TRAINING.md)。已经完成 10 轮的运行不能用 resume 重新开始；要做新实验需使用新运行配置/名称。

## 接口与后续对接

接口扩展为 `a-workflow-v2`，详见[真实视觉接口](REAL_VISION_API.md)。`mode=demo` 保留原流程；`mode=real` 读取配置的本地模型，禁止静默回退模拟结果。真实 Detection.is_demo=false，而 Inspection/Task.is_demo=true 表示仍使用模拟业务规则及位置场景。非空真实结果先审核，缺失模型返回 503；已有上传可在模型不可用时安全重放。

B 的 `a-task-query-v1` 不变。C 应更新巡检 schema、展示模型来源与真实检测/演示业务的区别，并更新 `a-knowledge-v2` 知识索引。

真实 HTTP 验收使用随机空闲本机端口、独立数据库和上传目录，未使用 8000，也未修改用户 PyCharm 服务。按文件顺序选取首张有标注的验证原图 `Czech_000006`，一次上传得到一项真实 longitudinal_crack 预测。请求中的 Jurong 坐标是模拟位置，非图片拍摄位置。通过审核创建一项任务后，再完成该任务，快照 revision 按 0→1→2 变化；上传/审核重试没有重复任务。停止独立服务后关闭模型并重启，同一上传仍可重放，已完成任务和历史保留；新 real 上传返回 503。11 个响应及日志保存在 `Dataset/evidence/http-acceptance/`。自动审核请求只测试接口，不表示专家确认检测正确。

在本机 PyCharm 的 Run Configuration → Environment variables 中设置：

```text
ROADGUARD_VISION_MANIFEST_PATH=Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/model_manifest.json
```

重启后通过现有上传接口发送 `mode:"real"`，不带 `scenario_id`。操作流程见[真实视觉接口](REAL_VISION_API.md)；默认不设此变量时仍可正常使用 demo。

## 空间清理

在训练完成、验证/测试评估成功、主 agent HTTP 与数据完整性验收通过后，先预览清单，再清理：

- 156 个冗余下载分块/哈希文件：2,611,938,166 字节；删除前重新核对完整 ZIP 的 SHA-256、绝对路径、文件白名单及无符号链接。
- 3 个可重建 YOLO 标签缓存：5,252,792 字节；仅清理 prepared/labels 下的 train/val/test.cache。
- 合计 **2,617,190,958 字节，约 2.62 GB（2.44 GiB）**。

原始 ZIP、图片/标注、划分/哈希、最佳/最新/两个恢复权重、配置、日志和评估证据均保留；未清除虚拟环境或共享系统缓存。清理记录在运行目录 `cleanup-*.json` 和 `Dataset/evidence/download-parts-cleanup-*.json`。再次训练/验证时小型标签缓存可自动生成。

## 验证证据

- 完整 Python 回归：**611 passed, 1 skipped**；跳过项为当前 Windows 用户无法创建符号链接的实文件测试，Linux CI 覆盖对应路径。一个 Starlette/httpx 弃用提示不影响结果。
- CI 保护脚本测试：**44 passed**；依赖一致性 `pip check` 通过。
- 实际 GPU 恢复 smoke、完整 10 epoch、验证/测试评估、隔离 HTTP、训练后数据哈希校验均通过。
- Dataset 整体忽略，提交前检查暂存区没有该目录；只上传代码、文档、配置示例与小型统计证据。

尚未定义业务准确率门槛或校准自动接受阈值。后续模型改进应依据训练/验证集开展；已经查看本轮测试集指标，需要保留其使用记录，不能反复按该结果调参后仍称其未使用测试集。
