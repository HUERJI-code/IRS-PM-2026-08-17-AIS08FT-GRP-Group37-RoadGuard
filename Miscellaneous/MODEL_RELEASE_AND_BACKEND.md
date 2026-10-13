# 当前模型发布与后端接入

日期：2026-10-13；负责人：A。本次按项目发起人要求发布最佳已训练权重并接入后端，不启动新训练。接口增量为 **a-workflow-v3**，FastAPI 文档版本 **0.6.0**；任务快照仍为 a-task-query-v1。

## 选用哪个模型

训练权重为 YOLO11s 的 balanced40/img832 实验 best（第 10 轮），与此前选定的最佳权重字节完全相同：

- 文件名：`roadguard-yolo11s-single-v1.pt`；19,218,837 bytes。
- SHA-256：`464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`。
- 八类：仍按 RDD2022ES 0～7，不合并宽/深等类型。
- 单图主要损伤场景：原图推理 832，原始置信度过滤 0.20，NMS IoU 0.70，最多保留 100 条原始检测；CPU FP32。
- 主建议：原始置信度 × 框面积占比的四次方根选一个。保留竞争类别/区域提示与全部原始框。

这里“最佳”指已完成实验中的权重与本场景的均衡选型，不表示每项指标都最高。多目标框检测曾选择原图加翻转配方；本次单主目标校准选择原图配方，两者使用相同权重。[单目标实验](SINGLE_DAMAGE_OPTIMIZATION.md)的 377 张确认图片上，图像级八类 Precision/Recall 为 **61.63%/61.99%**，两个 70% 仍未达到；这不是独立真实场景测试。已知明显坑洞照片与 AI 图仍失败。发布不改变 experimental 状态，所有真实非空结果仍需审核。

## GitHub 中保存什么

源代码、模型 manifest、评估摘要、测试和文档通过 PR 进入 main。权重作为同一**私有仓库**的 [vision-single-v1 Release](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard/releases/tag/vision-single-v1) 附件上传；有仓库权限的成员可下载。Release 可保存二进制附件，代码克隆与模型下载分别进行。[GitHub Release 说明](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)

用户本次授权只发布这一份部署权重。Dataset 图片、原始标注、完整预测、上传图、数据库、训练恢复保存点继续忽略；原有 `best`、`last`、`resume-latest` 和 `resume-previous` 不移动、不删除。仓库可见性保持私有。

## 组员首次安装

先拉取 main，在仓库根目录安装后端和可选视觉依赖。以下为 CPU 推理环境；现有 GPU 训练环境按训练指南保留，不必重装 PyTorch：

```powershell
python -m pip install -r SystemCode/backend/requirements.txt
python -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r SystemCode/model/requirements-vision.txt
```

登录 GitHub，从上面的私有 Release 下载 `roadguard-yolo11s-single-v1.pt`，再执行：

```powershell
.\.venv\Scripts\python.exe SystemCode/model/install_released_model.py --file "C:\Users\你的用户名\Downloads\roadguard-yolo11s-single-v1.pt"
```

安装器核对文件大小和 SHA-256，原子安装到 `Dataset/models/roadguard-yolo11s-single-v1.pt`。相同文件重复安装无影响；已有不同文件则拒绝覆盖。它不反序列化权重、不从其他网站找模型。

后端默认读取已提交的 [发布 manifest](../SystemCode/model/releases/roadguard-single-v1.json)。正常启动即可：

```powershell
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000 --reload
```

工作目录是仓库根目录。PyCharm 的 Parameters 与上述 `-m uvicorn` 后的参数一致；旧运行配置若显式指定 `ROADGUARD_VISION_MANIFEST_PATH`，它仍覆盖默认值，应改为 `SystemCode/model/releases/roadguard-single-v1.json` 或移除覆盖。设置该变量为 `disabled` 可关闭真实检测。

没有权重/依赖时仍能启动服务与使用 demo；首次 real 上传返回 503 `detector_unavailable`。不会自动下载或替换成模拟结果。安装或修复后重启进程。`/health` 只检查基础服务和数据库，不证明模型已加载。

## 测试 API 与新增字段

打开 `http://127.0.0.1:8000/docs`，向 `POST /api/v1/inspections` 上传 JPEG/PNG，Header `Idempotency-Key: real-test-001`，metadata 填：

```json
{"mode":"real","latitude":1.3405,"longitude":103.706,"road_type":"public_motor_road"}
```

位置只是演示输入，不能据此声称照片摄于 Jurong；道路类型仍由用户声明。real 模式不传 scenario_id。可执行完整响应样例在 [真实主建议示例](../SystemCode/contracts/workflow/real-primary-example.json)。

`inspection.primary_suggestion` 新增：

| 字段 | 含义 |
| --- | --- |
| policy_version / strategy / threshold | 本次上传冻结的选择配置 |
| detection_id | 指向 `detections` 的一个主建议；无候选为 null |
| ranking_score | 排序分数，不是正确概率，也不替代 Detection.confidence |
| ambiguous | 是否存在分数相近的其他类别或相离区域；false 不保证正确 |
| competing_detection_ids | 包含主建议及竞争结果的原始检测 ID |

普通 demo 或未配置主建议的旧 manifest 返回 `primary_suggestion:null`；默认发布模型无检测时返回该对象，但其中 detection_id/ranking_score 为 null。历史巡检缺少此字段时按 null 读取，不重新推理或重写其证据。

C 展示时从 `detections` 查找主建议 ID，默认画一个框；允许展开全部证据。歧义与低置信度均应提示审核。**`selected_detection_id` 仍表示原有流程的选择结果，不能拿主建议当已审核结果**。审核可以确认/纠正任何该巡检中保留的检测，并非只能选择主建议。

真实非空上传状态仍是 pending_review，task 为 null，input_revision 不变。确认/纠正后才生成唯一 Task 并递增版本；Task 与业务规则仍是 demo。相同上传重试、模型不可用时重读、重启与审核都保留原始主建议快照。SQLite schema 仍为 v2，无破坏性数据库迁移。

严格解析 a-workflow-v2 InspectionRecord、禁止额外字段的客户端须更新为 v3 并接受新增可空字段。Detection、Task、任务快照和审核请求字段没有更改。

## 验收

完成真实 CPU FP32 的七张已知图片 API 上传、与实验入口输出对照、重试、重启读取、关闭模型后的读取/503、人工审核与唯一任务快照检查。单元与回归结果、源哈希和完整本地证据位置记录在 [发布验收摘要](../SystemCode/experiments/vision/model_release_summary.json)。数值一致证明接入正确，不证明图片识别正确。
