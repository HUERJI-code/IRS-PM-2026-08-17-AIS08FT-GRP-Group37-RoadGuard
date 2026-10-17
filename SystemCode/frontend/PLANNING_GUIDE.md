# C 第 7 步：四队控制与显式重算

2026-10-17，负责人 C。现已写回原项目并完成队伍调整、重算、过期状态和地图联动的浏览器验收，详见 BROWSER_ACCEPTANCE.md。

## 使用与行为

打开 /routes。页面读取后端配置的全部队伍，显示可用/停用、基地与记录版本，不硬编码队伍数量。点击停用或启用仅保存状态，必须再点击“重算 GA 与 Greedy”才生成方案。

页面先读取队伍，再以相同 input_revision 获取完整活动任务快照；版本不一致要求刷新。上传结果、审核关联任务和任务详情都有统一重算入口。队伍修改成功后，使用返回版本重新核对快照，重算请求明确携带 expected_revision。未接受、完成和取消任务不混入活动快照。

重算结果显示同一次响应返回的 GA、Greedy 两个方案 ID、版本、开始时间、任务分配数和矩阵来源，再按 ID 查询保存方案。队伍停用或闲置仍显示；未分配任务使用后端原因。第 8 步地图已在原项目接入，见 MAP_GUIDE.md；第九步指标对比已完成，重算结果提供比较入口，见 COMPARISON_GUIDE.md。

## 并发与失败

- 队伍修改携带固定 request_id、expected_version、available。未知结果保留原请求重试，不生成新请求；冲突要求重新读取后选择新动作。
- 队伍修改成功但输入读取或重算失败时保留已保存状态，不回滚或重复 PATCH。旧方案仍显示，并按后端 is_stale 与已读取版本标为过期。
- 重算不具备幂等标识。网络/超时等未知结果不自动重算，先读取输入及已保存方案；最新方案不能证明属于上一请求。用户核对并勾选“仍要发起一次新的计算”后才允许新计算，明确可能重复。
- 重算成功但详情读取失败，保留成功响应并重试查询，不把读取失败误报为计算失败。
- Google 行程矩阵失败不切换模拟矩阵。前端只显示后端矩阵来源，未调用 Google 进行真实验收。
- 重算等待上限 120 秒；页面离开会取消前端等待，但不保证后端停止。未决请求只保存在内存，不能跨刷新或来源切换恢复。
- 未生成方案、空活动任务、服务失败明确区分；只读模拟来源禁止队伍修改和重算。

## 文件与接口

新增 src/pages/RoutesPage.tsx、RoutesPage.test.tsx、src/test/planning-fixtures.json、scripts/export_planning_fixtures.py；更新 App 路由和上传/审核/任务入口。无新增依赖，不修改 A/B 后端、公共契约、算法或数据库结构。

使用 GET /crews、PATCH /crews/{id}、GET /tasks/snapshot、POST /route-plans/recalculate、GET /route-plans/latest 和 GET /route-plans/{id}，统一 /api/v1 前缀与既有客户端。

## 验证

- 工作副本运行 npm run lint、npm run test:ci、npm run build。最终结果附于交付记录。
- 新增 15 项调度页面测试，包含 React StrictMode 挂载/取消场景，覆盖版本、原请求重试、重复点击、未知重算核对、空任务、只读模拟、方案读取失败、全部停用与未分配原因。
- export_planning_fixtures.py 通过真实 FastAPI TestClient 在临时 SQLite 中验证队伍修改和重放、旧版本 409、旧方案过期、同轮双方案以及全队停用返回 no_available_crew。使用合成图片、demo 检测和模拟行程矩阵；未动真实项目数据。
- 后端验证环境 Python 3.12，不代表 Python 3.11 全量后端测试通过。
- 原项目浏览器联调与手机布局验收已完成。构建保留单 JS 包超过 500 kB 的提示。

## 交付状态

代码与文档已写回原项目，未提交、未推送，无远端 CI 结果。最终验收见 BROWSER_ACCEPTANCE.md。

## 最终检查结果

2026-10-16：静态检查通过；7 个测试文件共 87 项测试全部通过；生产构建通过（JS 546.97 kB，gzip 152.65 kB，体积提示保留）。测试与构建均在可写副本执行。
