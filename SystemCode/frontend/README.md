# RoadGuard 前端 · C 第 2–9 步

负责人：C。当前实现 React + TypeScript 前端基础、六类页面导航、响应式布局、可访问性基础和真实健康检查。第 4 步已接入图片上传与检测结果、关联任务读取，详见 [上传使用说明](UPLOAD_GUIDE.md)；第 5 步已接入人工审核，详见 [审核使用说明](REVIEW_GUIDE.md)。第 6 步任务管理见 [任务说明](TASK_GUIDE.md)，第 7 步队伍控制与显式重算见 [调度说明](PLANNING_GUIDE.md)。第 8 步地图见 [地图说明](MAP_GUIDE.md)。第 9 步 GA / Greedy 同轮比较见 [比较说明](COMPARISON_GUIDE.md)。助手仍待接入。第 3 步已增加统一客户端、OpenAPI 生成类型与响应校验，以及明确切换的只读模拟样例；详见 [API 接入说明](API_CLIENT.md)。

## Mac 启动

使用 **Node 22 + npm**，与现有 CI 一致。Node 必须是 22.12 或更高的 22.x；目录中的 `.nvmrc` 供已经安装 nvm 的成员执行 `nvm use`。未安装 Node 时先安装 Node.js 官方 22.x 版本，然后确认：

```sh
node --version
npm --version
```

从仓库根目录启动前端：

```sh
cd SystemCode/frontend
npm ci
cp .env.example .env.local
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。环境文件可省略，默认后端地址为 `http://127.0.0.1:8000`；改地址使用 `.env.local` 的 `ROADGUARD_API_TARGET`，修改后重启前端。端口被占用时明确报错，不悄悄换端口。按 Ctrl+C 停止。

另开终端，从仓库根目录启动现有 FastAPI（已有虚拟环境可直接激活，不重复创建）：

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r SystemCode/backend/requirements.txt
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

健康检查无需安装或运行视觉推理；真实模型依赖按[后端说明](../backend/README.md)单独准备。后端启动会按既有行为初始化/验证其数据库；不要把已有数据库当测试临时文件删除。

## 页面与连接行为

| 前端地址 | 内容 |
|---|---|
| `/` | 跳转任务工作区 |
| `/inspections/new` | 图片、模式、位置与道路声明上传 |
| `/inspections/:inspectionId` | 巡检结果、单框图片与关联任务 |
| `/reviews` | 待审队列、确认、纠正与驳回 |
| `/tasks` | 任务列表、详情与状态管理 |
| `/routes` | 队伍控制、显式重算、Jurong 地图与路线详情 |
| `/comparison` | 同轮方案核对、指标与未分配原因比较 |
| `/assistant` | 路线助手骨架 |
| 其他路径 | 404 页面及返回入口 |

页面自动请求只读 `GET /api/v1/health`，有加载、成功、失败、8 秒超时和手动重试状态。上方数据来源面板可显式切换实时/模拟；展开“检查数据接入”后点击按钮，才读取活动任务快照和 GA 最新方案。应用与数据库成功不等于模型、Google 或助手就绪。失败不改用 mock；页面“未接入”不等同于任务为空。

Vite 开发服务器与本地构建预览把 `/api` 原样转发给后端，不需要更改 A 的 CORS。浏览器不存放后端密钥。`ROADGUARD_API_TARGET` 只供本地服务器使用，不使用 `VITE_` 前缀暴露秘密。

生产部署必须将 `/api` 反向代理到同一 FastAPI，并将其他页面请求回退到 `index.html`，支持刷新深层页面。`npm run preview` 仅用于本机构建检查，不是生产服务器。

## 检查与依赖

```sh
npm run lint
npm run test:ci
npm run build
npm run preview
```

预览地址 `http://127.0.0.1:4173`。`npm test` 是开发监视模式；CI 用 `test:ci` 单次运行。测试覆盖六页导航、首页跳转、直接路由、404、健康加载/成功/失败/重试、非法响应、超时与卸载取消。新增客户端与来源切换测试见 API_CLIENT.md；后端业务测试不在本次改动范围。

- React/React DOM：组件渲染；React Router：页面导航与浏览器历史。
- Vite/React 插件、TypeScript：开发代理、构建与类型检查。
- ESLint/TypeScript 与 React 规则：静态检查。
- Vitest/jsdom/Testing Library：真实组件交互与网络状态测试。
- 依赖固定在 package.json，唯一锁文件为 package-lock.json；使用 npm ci 复现。现有 CI 自动检测前端并运行 lint、test:ci、build，不需要更改 `.github`。

## 交接边界

本轮只修改 `SystemCode/frontend/`，不修改 A/B API、数据库、业务配置。六类页面不显示虚构队伍任务、路线或指标；助手交互仍按后续步骤实现。共享文档中“前端尚未实现”的旧描述应理解为完整业务应用未交付；当前基础状态以本说明为准。

## C 的任务规划与页面设计

[14 步任务清单](docs/C_TASK_PLAN.md)、[页面流程](docs/PAGE_FLOW.md)、[初始接口对照](docs/API_MAPPING.md)、[初始待对齐事项](docs/OPEN_QUESTIONS.md)保留规划时的基线。当前已实现第 1–9 步，验证边界以本目录各模块说明为准。
