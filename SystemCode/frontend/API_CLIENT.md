# C 第 3 步：API 客户端与模拟数据

所有实现位于前端目录，不改变 A/B 的 API 或数据库。当前覆盖已实现的健康、demo、巡检、审核、任务、队伍和路线接口；助手四接口仍为提案，未当成现有接口接入。

## 类型与运行时检查

- `src/api/generated/openapi.json`：当前 FastAPI 导出的接口快照。
- `src/api/generated/schema.d.ts`：openapi-typescript 自动生成的完整类型，业务代码使用 `Model<'TaskRecord'>` 等别名。
- `src/api/contracts.ts`：用同一快照中的 JSON Schema 校验所有 JSON 响应，不强制转换数字、不补默认值、不丢弃未知字段。HTML 回退页、缺字段、错误类型会明确失败。
- multipart 的 metadata 未在后端 OpenAPI 中展开，其 `UploadMetadata` 联合类型按当前 Python schema 手动定义：real 不允许 scenario_id，demo 必须提供 scenario_id。图片使用独立 URL 校验助手。
- JSON Schema 不包含 Pydantic 的所有跨字段业务校验；优先级、规则、审核与路线合法性仍由后端负责，前端不复制业务算法。

从前端目录维护接口快照（使用安装了后端 requirements-ci.txt 的 Python 环境）：

```sh
python scripts/export_contract.py --check
# 只有后端契约确实变更且准备更新快照时：
python scripts/export_contract.py
npm run api:types
npm run test:ci
npm run build
```

生成脚本调用现有应用工厂，使用独立临时数据库、显式 demo 检测和模拟行程矩阵，不访问真实项目数据库或付费 API。生成结束清理临时数据库。`--check` 只比对当前后端 OpenAPI，不生成样例或运行规划。生成记录在 provenance.json；样例的随机 ID、时间和算法耗时会随重新生成变化，不能作为实验结果。不要手动修改生成类型来掩盖后端变化。

新增依赖：ajv / ajv-formats 用于当前 JSON Schema 校验；openapi-typescript 用于生成类型。生成器要求 TypeScript 5.x，因此从第 2 步的 6.0.3 调整为 5.9.3，遵循 peer dependency，不使用强制安装。Node 22、npm、唯一 package-lock 不变。

## 页面如何调用

页面在 ApiProvider 内通过 `useApi()` 获取 `api`、`mode`、`imageUrl`。真实模式统一 `/api/v1`，沿用开发代理，无需在页面硬编码后端主机。客户端共 16 个 JSON 方法；第 17 个图片接口通过 imageUrl 解析后作为图片源读取。

| 领域 | 方法 |
|---|---|
| 基础/演示 | health、demoScenarios、demoAssessment |
| 巡检 | upload、inspections、inspection、review |
| 任务 | tasks、snapshot、task、updateTask |
| 队伍 | crews、updateCrew |
| 方案 | recalculate、latestPlan、plan |

所有方法支持 AbortSignal。切换数据来源会取消旧读取并清空旧显示，防止跨来源混用。默认超时 8 秒，第 4 步上传覆盖为 120 秒；后续真实大规模重算可创建配置了更长 timeoutMs 的客户端，但不能通过自动重试掩盖超时。上传原样发送 image + metadata，不手写 multipart Content-Type 边界。图片 URL 只接受同源 `/api/v1/inspections/{32位hex}/image`。

## 幂等、版本与错误

审核/任务修改/队伍修改先创建一次 `createOperation(payload)` 并保存；其 requestId 与 payload 副本固定。同一逻辑操作重试必须复用同一对象；用户改内容或刷新后重新确认新的记录版本，创建新对象。上传调用者同样必须保存图片、metadata 和一个请求 key，不能每次重试重新生成 key。

`expected_version` 是单记录版本，`expected_revision` 是全局规划输入版本。客户端不会自动更新旧版本、偷偷重放旧意图或进行任何自动重试。B 的重算没有幂等 key，超时/网络中断后应先核对结果，不自动再次重算。

ApiError 保留 code、status、kind、details、outcomeUnknown。用户提示按 code 映射，不匹配后端英文 message。写入后遇网络/超时或损坏的响应，显示结果尚不确定；前端不能据此断言操作没有发生。统一组件提供加载、空列表、无方案和错误显示。已提交前的主动取消不标记为未知写入结果。

时间显示统一 Asia/Singapore；无时区时间字符串拒绝显示为有效时间。路线分钟偏移叠加在 planning_start_at 上。formatMinutes 与 formatRuntime 分别显示分钟与毫秒；null/undefined 显示未提供，零仍显示零。

## 显式模拟模式

页面上方“数据来源”可选实时后端、模拟正常、模拟空数据、模拟服务失败、模拟版本冲突。刷新页面恢复实时后端模式；不会持久化一个容易遗忘的模拟开关。模拟模式始终显示说明，也不把模拟健康响应称为真实数据库连接。

展开“检查数据接入”，点击“读取当前来源”，可以验证活动任务数量及 GA 方案是否存在。只有显式点击才请求任务/方案；导航不会执行写入。

- 正常样例：后端生成的 accepted、pending_review、no_detection 三种巡检，一个活动任务，四队，同轮 GA/Greedy 保存方案。
- 空样例：空巡检/任务，四队配置，无保存方案。无方案返回 route_plan_not_found，不伪造空 RoutePlan。
- 失败/冲突样例：结构化 503 database_unavailable / 409 stale_input_revision。
- 模拟读取支持列表状态过滤、分页和指定 ID；快照版本不一致返回冲突。
- **目前是固定只读样例，不是可写模拟后端。** POST/PATCH 明确返回本地 mock_write_unavailable；不会声称保存成功或偷偷转发真实请求。后续上传/审核页面需要完整状态演示时，应另增加对应的隔离场景，不能在浏览器重写 A/B 业务算法。
- mock 图片为生成的纯色 PNG；不是道路照片或模型效果证据。示例返回的服务端图片路径在模拟模式映射为该图，避免访问真实记录。

## 验证边界

当前自动测试覆盖生成样例 schema、请求路径/字段、multipart、请求 ID 复用、版本冲突、无自动重试、超时/取消、非法响应、图片地址、分页、显式来源切换、禁止模拟写入、单位和时区。第 4 步已接入真实上传与详情页面，见 UPLOAD_GUIDE.md；第 5 步审核界面已接入，见 REVIEW_GUIDE.md；第 6 步任务编辑和第 7 步队伍控制已实现；重算显式调用并核对输入版本，见 TASK_GUIDE.md 与 PLANNING_GUIDE.md，不宣称完整调度业务端到端通过。
