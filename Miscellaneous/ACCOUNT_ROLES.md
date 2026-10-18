# 账号、页面与接口权限

2026-10-18 · A 统筹共享认证与前端联调。用户明确要求不同账号进入不同工作区；本模块随用户批准的统一前端与施工队工作台一并交付，前后端须一起更新。

## 三种账号

| 角色 | 登录后入口 | 可以做什么 | 不能做什么 |
|---|---|---|---|
| `inspector` 巡查员 | `/inspections/new` | 上传一张照片、查看自己上传的巡检结果与照片 | 查看全局巡检/任务列表、审核、调度、修改任务 |
| `crew` 施工队 | `/crew` | 查看固定绑定队伍的最新 GA 路线、对应任务/照片、确认本队任务完成 | 切换其他队、读取全局列表、改标签/位置、取消任务、重算路线 |
| `dispatcher` 中央调度员 | `/tasks` | 人工审核、任务管理、四队管理与规划、算法比较、路线助手入口 | 上传照片、进入施工队工作台 |

巡检详情是所属工作流程的附属页面。巡查员只能读自己的巡检；施工队只能读本队可访问任务对应的巡检；调度员可读全部。路线助手保留现有开发中状态，本次不实现 GPT/RAG。

前端根据服务端账号过滤导航并拦截不属于该角色的页面地址。后端独立鉴权，不能靠改网址、请求头或前端状态绕过权限。`/crew?crew=crew-01` 不改变账号绑定；工作台接口不接受客户端指定的队伍或算法。

## 本机开通账号

没有公开注册入口、默认密码或启动时自动创建的账号。由项目负责人在仓库根目录执行以下 PowerShell 命令；密码在终端隐藏输入，长度 12～256 字符。

```powershell
$env:PYTHONPATH = 'SystemCode/backend'
# 如果后端使用自定义数据库，必须设置为同一个 ROADGUARD_DB_PATH。
.\.venv\Scripts\python.exe -m roadguard.auth.manage create a --name '巡查员 A' --role inspector
.\.venv\Scripts\python.exe -m roadguard.auth.manage create b --name '施工队 2 · B' --role crew --crew crew-02
.\.venv\Scripts\python.exe -m roadguard.auth.manage create c --name '中央调度员 C' --role dispatcher
```

账号名忽略大小写，允许英文字母、数字、点、下划线、连字符，最长 32 字符。角色和队伍只能在服务端配置。其他施工队分别绑定 `crew-01`、`crew-03`、`crew-04`；多人可有各自账号并绑定同一队。账号不会因为拉取仓库而共享，必须在实际运行数据库中创建。

重置密码：`python -m roadguard.auth.manage password b`。停用账号：`python -m roadguard.auth.manage disable b`。重置/停用会撤销该账号会话。`--generate-password` 仅供本地生成随机密码，会显示一次，勿保存到可提交的文件。没有网页账号管理或找回密码流程。

## HTTP 接入与 Swagger

| 接口 | 响应/作用 |
|---|---|
| `POST /api/v1/auth/login` | 请求 `{ "username": "a", "password": "本地设置的密码" }`，设置 HttpOnly Cookie，返回 `user`、`csrf_token`、`expires_at` |
| `GET /api/v1/auth/session` | 当前账号及 CSRF token；未登录/过期返回 401 |
| `POST /api/v1/auth/logout` | 撤销当前会话并清 Cookie；需要 `X-CSRF-Token` |
| `GET /api/v1/crew/workspace` | 固定所属 `crew`、最新 GA 的本队 `plan`、该路线当前 `tasks`、`input_revision`；无方案时 `plan=null` |

`user` 只有账号 ID、账号名、显示名、角色与可空的 crew_id。`expires_at` 是 Unix 秒，属于认证会话字段；业务记录时间仍使用带时区 ISO 8601。工作台 `plan` 仅含本队路线及基地/时间/来源，不返回别队路线、全局矩阵或全局指标。

在同一个主机名的 `/docs` 中先执行 login，浏览器自动保留 Cookie。复制响应中的 `csrf_token` 到写接口的 `X-CSRF-Token` 输入框，再执行上传、审核或完成任务。GET 不要求 CSRF。换角色先 logout，再 login；401 重新登录，403 表示角色/CSRF/来源不允许，404 可能是对象不存在或不属于当前账号。不要混用 `localhost` 与 `127.0.0.1` 的 Cookie。

脚本客户端保存登录 Cookie，并在写请求发送 `X-CSRF-Token`；API 客户端不再匿名调用业务接口。`/health` 和 OpenAPI 文档仍可匿名访问。新业务路由必须加入 `auth/dependencies.py` 权限表，否则默认拒绝。

## 归属、并发与审计

- SQLite 从 v3 增量迁移至 v4，新增 `auth_users`、`auth_sessions`、`auth_login_limits`、`inspection_owners`、`auth_audit`。保留原巡检、任务、图片、方案、请求键和 input_revision，不重建数据库。首次迁移需要写锁；关闭数据库查看器未提交事务后启动。
- 新上传同一事务记录巡查员归属；上传/审核/完成的幂等键按账号隔离。旧巡检没有已核验的上传者，不会自动归给第一个登录者；调度员仍可查看，施工队按任务归属查看。
- 本队任务归属取最近保存 GA 方案。当前没有独立的“发布方案”步骤；调度保存 GA 就会改变工作台依据。单纯 input_revision 变化会提示旧快照，不禁止仍分配给本队的有效任务完成。
- 完成写入在同一写事务检查账号仍有效、任务仍在本队最新 GA 路线、队伍可用、任务版本及状态，避免改派后旧页面误操作。已提交完成的原请求可在重算后重试，凭本队完成收据校验；不会重复修改或自动重算。
- 完成事件记入 `auth_audit`（账号、任务、请求、队伍、方案、时间），任务历史新增 `actor_source=authenticated_user`。旧 `user_declared_unverified` 保持原义；登录记录身份不代表工程专业资质认证。

## 会话与运行配置

密码采用 Python 标准库 scrypt（N=2^17、r=8、p=1、随机盐），数据库只存密码哈希。会话是 32 字节随机值，数据库只存 SHA-256 摘要，8 小时过期。Cookie 使用 HttpOnly、SameSite=Strict；写请求校验会话对应的 CSRF token 和请求来源。密码/token 不写入前端 localStorage；跨标签页只保存无凭据的状态变更通知。

登录限制按账号 10 次、来源地址 60 次/15 分钟计数（成功登录清账号计数），存于数据库。Vite 代理下多个客户端可能共用来源地址计数。当前适用于本地项目预览，部署至外部网络应使用 HTTPS，并设置 `ROADGUARD_AUTH_COOKIE_SECURE=true`；`ROADGUARD_AUTH_ALLOWED_ORIGINS` 用逗号列出实际前端来源。默认只允许本地 127.0.0.1/localhost 的 5173、4173、8000、8001 端口；不自动开放局域网。

实现依据：[OWASP 密码存储建议](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[OWASP 会话管理建议](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)。当前未加入 SSO、MFA、自助账号管理或正式生产部署流程。

## 验收入口

真实鉴权测试：`python -m pytest SystemCode/tests/test_auth.py -q`，包括匿名拒绝、三类角色、上传归属、跨队拒绝、改派/停用、CSRF、会话撤销/过期、登录限流、幂等完成、v3 数据保留迁移。

前端：`npm run lint`、`npm run test:ci`、`npm run build`。覆盖登录、错误重试、角色导航、直接地址保护、换账号清除旧页面、跨标签会话变化、固定本队工作台及手机任务选择。

历史业务单测和合成 fixture 导出显式使用 `SystemCode/tests/auth_test_support.py` 的隔离测试身份；生产应用不加载该覆盖。账号安全测试使用真实登录与 Cookie，不覆盖鉴权依赖。前端/后端需要同时更新；旧匿名脚本须适配登录。
