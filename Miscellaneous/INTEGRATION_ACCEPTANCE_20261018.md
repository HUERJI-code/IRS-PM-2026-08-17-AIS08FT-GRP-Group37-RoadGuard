# A/B/C 前后端联调验收记录

日期：2026-10-18；执行人：coding agent 代表 A；范围：用户已拉取的 B 调度与 C 前端，以及现有 A 真实模型/业务接口。结论：现有主流程已在本机跑通；修复一项仅在真实视觉依赖加载后出现的上传错误。助手尚未实现，真实 Google 行程服务未在本轮验收，不能据此宣布全部项目完成。

## 1. 代码与运行隔离

- 基线 `4fa0c38`（`feat: implement frontend foundation`）；读取远端后确认与 `origin/main` 一致。
- 修复分支 `fix/integration-image-decoder`；验收完成时为本地状态，随后按用户要求通过独立 PR 交付。GitHub 检查与合并状态以该 PR 为准；本记录不将后续前端优化计入本次验收。
- 既有 YOLO context-crop 训练相关未提交改动保留，没有训练或修改部署权重。
- Python 3.12.14、Node 22.23.3、npm 10.9.9；前端严格按 `package-lock.json` 执行 `npm ci`。此记录不代替 Python 3.11 的远端 CI。
- 前端 `http://127.0.0.1:5173`；独立后端 `http://127.0.0.1:8001`；Swagger `http://127.0.0.1:8001/docs`。前端 `/api` 原样代理到 8001。
- SQLite：`Dataset/acceptance/integration-20261018/workflow.sqlite3`；图片位于同目录的 `uploads/`。未使用常用业务库，未停止或修改用户的 8000 服务。
- 明确设置 `ROADGUARD_TRAVEL_MATRIX_PROVIDER=simulated`。规划使用现有 B 演示参数：四队、NUS-ISS 起点、480 分钟班次、需要返基地；没有将这些参数升级为真实运营标准或新增已确认业务决定。
- 模型使用已提交的 `roadguard-yolo11s-single-v1.pt`，SHA-256 为 `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`。正常 CPU 推理，无训练，无模型下载。

## 2. 实际浏览器验收

浏览器使用实时后端接口。除专门验证错误页面时显式选取只读模拟失败样例外，业务操作均调用隔离库中的真实 API。

| 操作 | 实际结果 |
| --- | --- |
| 首页及空活动列表 | 应用与数据库连接成功，初始任务为 0，无方案与空方案区分显示 |
| 选择本地图片并上传真实推理 | 使用既有 `05-pothole-asphalt.png` 测试图，上传成功，详情显示部署模型、一个框和约 25.3% 的 `alligator_crack`，进入人工审核 |
| 人工纠正并接受 | 将上述测试记录纠正为 `pothole`，创建 P2/120 分钟任务；保留原标签、置信度和审核历史 |
| 单任务规划 | GA/Greedy 同轮成功，包含四支队伍；一队已分配、三队闲置；地图包含 Jurong 与区域外 NUS-ISS |
| 停用 Crew 01 | 保存状态后原方案明确过期；显式重算后该队仍显示为停用，任务分给其他队伍 |
| 完成任务 | 通过任务页面保存完成状态，记录变只读，保留历史，从活动列表移除，提示规划输入变化 |
| 20 任务地图与比较 | 页面读取全部活动任务；重算生成两份保存方案，四队各有 3 站，另有 8 个未分配任务和原因；GA/Greedy 地图可切换 |
| 同轮比较保护 | 从重算结果进入显示“同轮方案已核对”；本次 20 任务方案分配集合不同，页面不计算时间/目标值改善率；直接打开比较页明确缺少同批次凭据 |
| 显式失败样例 | 选择“模拟·服务失败”显示结构化错误并撤下未核实指标；切回实时恢复读取。这是受控前端失败样例，不是真实 Google 故障 |
| 助手页面 | 明确显示“业务功能尚未接入”，没有把占位页计为通过 |

照片的测试坐标 `1.3405, 103.706` 是合成 Jurong 位置，不能作为该照片拍摄地点的证据。模型将坑洞样例判为龟裂，说明现有识别质量问题仍在；本轮验证的是模型接入、分流与人工纠正链路，**不代表 Precision/Recall 达标**。

## 3. 真实 HTTP 与自动检查

20 组本地 HTTP 验收通过，共 201 个请求，均经前端 5173 代理访问后端。覆盖：

- 四字段上传、单框详情、高置信度自动建任务、0.60/0.5999 边界、相同 key 重放。
- 真实 YOLO 已加载后的损坏图片校验；越界与无效图片拒绝且不改变任务/输入版本。
- 低置信度确认、纠正、驳回，无检测不建任务；审核旧版本 409、重复确认不重复写历史/任务。
- 标签修正重新计算 P3/P2/P1 对应 60/120/240 分钟；非法位置修改原子拒绝；完成/取消退出活动快照且保留历史。
- 队伍停用、重复变更、旧方案过期、旧输入重算 409、全队停用后每个任务都有 `no_available_crew` 原因。
- 空队列、1/10/15/20 个任务；四队可辨，任务在已分配与未分配中恰好出现一次；维修分钟取自保存 Task，基地及返程行程纳入统计，每队总工时不超过 480 分钟。
- GA/Greedy 同输入版本、开始时间、设置及模拟矩阵；在线 GA 记录 Greedy 初始解，不比本轮 Greedy 的优先级/目标评分更差。

| 任务数 | Greedy 已分配 / 未分配 | GA 已分配 / 未分配 |
| --- | --- | --- |
| 0 | 0 / 0 | 0 / 0 |
| 1 | 1 / 0 | 1 / 0 |
| 10 | 10 / 0 | 10 / 0 |
| 15 | 12 / 3 | 12 / 3 |
| 20 | 12 / 8 | 12 / 8 |

15/20 个任务的未分配原因均为 `exceeds_shift_limit`，P1 未分配数为 0。表中任务通过上传/人工纠正写入 SQLite，采用共享合成任务位置与标签；它是流程验收，不是新的算法性能实验。

| 检查 | 结果 |
| --- | --- |
| `npm run lint` | 通过 |
| `npm run test:ci` | 10 文件，127 项通过 |
| `npm run build` | 通过；JS 682.86 kB / gzip 183.90 kB，保留超过 500 kB 的单包提示 |
| `python SystemCode/frontend/scripts/export_contract.py --check` | 前端快照与当前后端 OpenAPI 一致 |
| `python -m pytest SystemCode/tests -q` | 最终 979 项通过、1 项 Windows 符号链接权限跳过；52.09 秒；保留 Starlette TestClient 弃用警告 |
| `python .github/scripts/check_repository.py` | 357 个文件检查通过 |
| `git diff --check` | 通过 |

上述本地检查使用保留既有训练改动的工作区，979 项计数包含那些未提交的训练测试，不代表本 PR 新增了这些测试。独立 PR 仅提交上传解码修复、对应回归测试及知识/验收文档；远端 CI 在干净检出上验证实际交付内容。

## 4. 发现和修复

真实 YOLO 首次加载后，Ultralytics 8.4.176 会全局替换 `PIL.Image.open`。损坏 PNG/无效字节触发其可选 HEIF 插件分支，本机没有 `pi_heif`，导致 `ModuleNotFoundError` 和 HTTP 500。普通 CI 注入假模型，不导入 Ultralytics，因此原测试未触发这个组合。

修复：上传模块在应用正常启动、YOLO 延迟导入之前保留 Pillow 解码函数引用，验证与二次解码始终使用这个引用，不跟随视觉包对全局函数的替换。保持 JPEG/PNG 限制、EXIF 规范化、像素/字节上限及原有错误契约，不额外安装 HEIF 插件。

新增 HTTP 回归用例复现“可选视觉库替换解码函数后，无效数据不应导致 500”：修复前失败，修复后通过；随后在实际服务中再次加载真实 YOLO，再上传损坏图片，得到 `422 invalid_image`，未创建记录。67 项图片/工作流定向测试通过，1 项 Windows 符号链接权限测试跳过。

源码改变需要同步知识包引用摘要；更新为 `a-knowledge-v7`，同时修正已发现的 qa-03 过期断言“真实检测一律先审核”。六份正文与业务规则版本保持不变；该资料更新不等于 RAG 服务已完成，也不代表所有历史阶段文字已经复核。

## 5. 尚未验收与交接

- **C 的 GPT/RAG 与队伍调整预览/确认尚未实现**：没有助手后端路由，本轮不能覆盖清单 BC07/BC08。
- **真实 Google 行程矩阵未调用**：本轮用明确模拟矩阵，未花费外部 API 用量；Google 错误边界由现有假传输自动测试覆盖，不代替真实服务验收。
- 地图为 SVG 路线顺序示意，`geometry=null`，没有道路导航折线；这是现有实现的明确边界。
- 本轮浏览器验证为桌面视口，没有重复手机尺寸或跨浏览器验收。
- 根规范及部分旧说明仍有 B/C 待实施的历史文字；当前实现进度以本记录及模块 README 为准。助手摄取前仍需清理过期的知识阶段表述。
- 权重、60% 阈值、单框及 P3/P2/P1 工时保持不变；模型泛化质量继续单独优化。

## 6. 复核证据及运行方式

原始证据只在本地 `Dataset/acceptance/integration-20261018/`，不提交 Git：

- `api-acceptance.json`、`http-trace.json`：20 组最终结果、请求 key、HTTP 状态及实际响应。
- `http_acceptance.py`：本次本地执行脚本快照，含上述浏览器预置记录 ID；不是可直接在常用数据库反复执行的通用导入器。
- `api-acceptance-before-fix.json`、`http-trace-before-fix.json`：首次失败证据；`retry-preparation-trace.json` 保留关闭上轮测试任务的操作。
- `api-final-snapshot.json`：20 个活动测试任务与输入版本 53；测试结束保留四队可用和测试方案，方便人工复查。
- `pytest-final.log`：最终完整后端回归；`pytest-source-hash-before-sync.log` 保留修复后发现知识包源码摘要需同步的检查结果。
- `ui-real-inspection.png`、`ui-comparison-single.png`、`ui-map-20-tasks.png`、`ui-comparison-20-tasks.png`：实际浏览器画面。
- 后端/前端 `.log` 与 `.pid`：本轮本机服务日志及启动进程记录。

若需重新启动同一隔离环境，在仓库根目录另开后端终端：

```powershell
$env:ROADGUARD_DB_PATH='Dataset/acceptance/integration-20261018/workflow.sqlite3'
$env:ROADGUARD_UPLOAD_PATH='Dataset/acceptance/integration-20261018/uploads'
$env:ROADGUARD_TRAVEL_MATRIX_PROVIDER='simulated'
$env:ROADGUARD_VISION_MANIFEST_PATH='SystemCode/model/releases/roadguard-single-v1.json'
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8001
```

前端终端使用 Node 22.12+ 的 22.x 与 npm，从仓库根目录执行：

```powershell
cd SystemCode/frontend
npm ci
$env:ROADGUARD_API_TARGET='http://127.0.0.1:8001'
npm run dev
```

端口已被本轮服务占用时不要重复启动；直接打开现有网址。所有上述配置用于独立联调库，与默认 8000/常用数据库配置分开。
