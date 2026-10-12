# RoadGuard 分支、PR 与 CI 使用说明

更新：2026-10-12。此文说明已提交的 CI 配置及其适用边界；每次运行结果以 GitHub Actions 页面为准。

## 1. 组员日常流程

1. 接受仓库邀请，使用自己的 GitHub 账号克隆仓库。先读根目录 [AGENTS.md](../AGENTS.md)。
2. 在工作区没有未处理修改时更新 `main`，为本次任务创建短期分支。
3. 完成实现、相关测试与文档后，提交并推送自己的分支。
4. 在 GitHub 创建 Pull Request，目标分支选择 `main`，按自动出现的 PR 模板填写。
5. 创建 PR 或继续向该分支推送提交，都会自动运行 RoadGuard CI；查看最新提交的 Checks。
6. 按项目发起人的约定，PR 无需另一位成员人工审核或批准。完成改动自检、适用检查通过且分支已同步最新 `main` 后，由 A 统筹 Squash and merge；agent 在获得合并任务授权后执行。若有冲突，先在功能分支同步 `main` 并解决，再推送重新检查。
7. 合并到 `main` 后自动再运行 CI，验证合并后的版本。若失败，由对应成员发修复 PR；不会自动回滚已合并代码。

示例（仅在没有待处理的本地修改时执行）：

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/b-greedy-planner
# 完成本次任务及本地验证，再按具体文件添加改动
git add <本次修改的文件>
git commit -m "feat(routing): add greedy planner"
git push -u origin feature/b-greedy-planner
```

之后在 GitHub 的 Pull requests 页面点击 New pull request，选择该分支 → `main`。推送尚未建立 PR 的功能分支不会启动 CI，以避免重复消耗额度；建立 PR 后的每次更新自动重跑。也可以在 Actions 页面手动运行工作流。

不要用 force push 解决同步失败，不把其他成员的修改加入自己的提交，不直接把日常开发推到 `main`。`main` 在待合并期间发生变化时，先同步并等待新的检查结果；当前套餐没有强制“分支必须最新”的保护。

## 2. 自动检查具体做什么

配置文件：[ci.yml](../.github/workflows/ci.yml)。权限仅为 `contents: read`，工作流不自动推送、不批准 PR，也不执行部署。

| GitHub 检查 | 当前/后续行为 |
| --- | --- |
| Repository checks | 检查课程目录及规范文件、JSON、四队/Jurong 默认配置、Markdown 本地文件链接、未解决的合并标记、Python 语法和误提交的部分本地产物；运行 CI 脚本自身的回归测试 |
| Python tests | 发现后端、模型、实验或共享测试目录中的 Python 代码后，安装明确的 CI 依赖并运行 pytest；没有业务代码时显示 skipped |
| Frontend checks | 发现前端代码或 package.json 后，运行 npm ci、lint、test:ci、build；没有前端实现时显示 skipped |
| CI | 汇总以上结果；必须通过仓库检查，且所有已存在模块的检查成功；失败、取消或意外跳过都不能得到通过结论 |

目前业务模块尚未实现。Python/前端检查跳过只代表“没有对应代码”，不代表业务测试通过。检查脚本无法证明所有逻辑正确，提交者或 agent 仍须按改动完成自检；本项目不把人工审核设为 PR 门槛。Markdown 检查仅验证本地文件目标，不检查远程网页或标题锚点。

## 3. A/B/C 后续如何接入真实测试

为统一运行环境，本 CI 使用 Python 3.11、Node 22、npm 和 Ubuntu 标准 runner。首次业务环境搭建须采用这些版本，或在同一 PR 中协调修改 CI 与开发说明。

**A/B：Python 模块**

- 新增第一批业务 Python 文件时，同时提供 `SystemCode/backend/requirements-ci.txt`，包含固定版本的 pytest 和本次测试所需依赖；若引用其他依赖文件，路径须支持从仓库根目录安装。
- 将单元/集成测试放在 `SystemCode/tests/`，按模块分子目录，使用 pytest 默认的 `test_*.py` 或 `*_test.py` 命名。
- CI 从仓库根目录执行 `python -m pip install -r SystemCode/backend/requirements-ci.txt`，然后执行 `python -m pytest SystemCode/tests -q`。测试应通过可重复的安装或项目配置导入模块，不依赖个人机器的路径。
- 不存在依赖声明或测试文件会失败；pytest 收集到零个测试也会失败。模型训练、下载完整数据集或调用收费 API 不放入普通 PR 测试，使用小样例与可替换服务验证逻辑。

**C：前端**

- 提交 `SystemCode/frontend/package.json` 和匹配的 `package-lock.json`，统一使用 npm。
- 提供可执行的 `lint`、`test:ci`、`build` 脚本和至少一个 `*.test.*` 或 `*.spec.*` 测试文件。
- `test:ci` 必须一次执行后退出，测试失败或没有收集到测试应返回非零状态；不能用 echo、`--passWithNoTests` 或忽略退出码伪造通过。
- 不注入真实服务密钥；外部模型、行程服务和 GPT 请求使用明确的测试替身。

本地检查 CI 基础设施，在仓库根目录执行：

```bash
python -m unittest discover -s .github/scripts -p "test_*.py" -v
python .github/scripts/check_repository.py
```

## 4. 当前套餐的限制

2026-10-12 查询此私有仓库时，GitHub 的分支保护和 rulesets 接口均返回：需要升级 GitHub Pro 或变更仓库可见性。仓库继续保持私有，不因设置 CI 改为公开。

- 当前流程：功能分支、PR、改动自检、自动 CI、执行合并和合并后 CI；无需人工批准。
- 当前无法强制：禁止直接推 main、必须一人批准、必须 CI 通过才允许合并，以及 GitHub 原生自动合并。
- 不使用自建机器人绕过上述限制，也不让 PR 中的代码拿到用于写入/合并的密钥。合并执行方主动核对最新提交的 CI、主分支同步状态和冲突情况。取消人工审核不启用原生自动合并；仅要求创建 PR 时，交付停在 PR 与检查结果。

如果以后账户获得支持私有仓库保护的套餐，A 可对 `main` 启用：必须 PR、要求 `CI` 检查且分支保持最新、处理未解决的问题、禁止强制推送和删除、管理员也遵守；所需人工批准数量保持为零。获得自动合并配置授权后，再开启仓库 Auto-merge，并在具体 PR 中启用。此次没有开通付费套餐或原生自动合并。

## 5. 费用与运行限制

GitHub Free 的 Actions 标准 runner 每月含 2,000 分钟，按账户共享；私有仓库的原生自动合并和分支保护需要 Pro 等支持的套餐。这里采用标准 Linux runner，不使用付费的大型 runner、不保留构建产物、不启用依赖缓存，单个任务设置 2～10 分钟超时，并取消同一 PR 的旧运行。

额度内无需额外付费；超过额度是否停止或产生费用，取决于账号付款方式及预算设置。此次没有查看剩余额度或更改账单/预算，不能保证账户其他项目不会耗尽额度。

官方参考：[套餐](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)、[Actions 计费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[自动合并](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request)。
