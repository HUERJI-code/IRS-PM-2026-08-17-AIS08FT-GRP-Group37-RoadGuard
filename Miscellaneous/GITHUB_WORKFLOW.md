# RoadGuard 分支、PR 与 CI 使用说明

更新：2026-10-12。此文说明已提交的 CI 配置及其适用边界；每次运行结果以 GitHub Actions 页面为准。

## 1. 组员日常流程

1. 接受仓库邀请，使用自己的 GitHub 账号克隆仓库。先读根目录 [AGENTS.md](../AGENTS.md)。
2. 在工作区没有未处理修改时更新 `main`，为本次任务创建短期分支。
3. 完成实现、相关测试与文档后，提交并推送自己的分支。
4. 在 GitHub 创建 Pull Request，目标分支选择 `main`，按自动出现的英文 PR 模板填写。标题、正文、摘要、评论和合并说明全部用英文。暂不合并时创建 Draft PR。
5. 创建 PR 或继续向该分支推送提交，都会自动运行 RoadGuard CI；查看最新提交的 Checks。
6. 按项目发起人的明确授权，普通就绪 PR 通过下述条件后，由 RoadGuard Auto Merge 自动 Squash merge，无需人工审核、批准或再次点击合并。若落后于 `main` 或有冲突，先在功能分支同步并解决，再推送重新检查。
7. 机器人合并成功后显式触发 `main` CI，验证合并后的版本；账号/agent 合并则由 push 事件触发。若失败，由对应成员发修复 PR，不自动回滚。涉及 `.github/` 的 PR 由 agent 完成自检和 CI 核对后合并，无需人类确认。

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

检查配置：[ci.yml](../.github/workflows/ci.yml)。检查工作流权限仅为 `contents: read`。独立的[自动合并工作流](../.github/workflows/auto-merge.yml)在 CI 完成后核对合并条件；两个工作流都不执行部署。

| GitHub 检查 | 当前/后续行为 |
| --- | --- |
| Repository checks | 检查课程目录及规范文件、JSON、四队/Jurong 默认配置、Markdown 本地文件链接、未解决的合并标记、Python 语法和误提交的部分本地产物；运行 CI 脚本回归测试，检查英文 PR 标题/正文 |
| Python tests | 发现后端、模型、实验或共享测试目录中的 Python 代码后，安装明确的 CI 依赖并运行 pytest；没有业务代码时显示 skipped |
| Frontend checks | 发现前端代码或 package.json 后，运行 npm ci、lint、test:ci、build；没有前端实现时显示 skipped |
| CI | 汇总以上结果；必须通过仓库检查，且所有已存在模块的检查成功；失败、取消或意外跳过都不能得到通过结论 |

当前已加入后端基础和公共 schema，Python tests 必须执行；前端尚未实现，因此 Frontend checks 仍显示 skipped。跳过只代表没有对应模块，不代表测试通过。检查脚本无法证明所有逻辑正确，提交者或 agent 仍须按改动完成自检；本项目不把人工审核设为 PR 门槛。Markdown 检查仅验证本地文件目标，不检查远程网页或标题锚点。

英文检查要求非空标题/正文，只接受拉丁字母、数字、标点等字符；允许 Markdown、URL、重音拉丁字母与 emoji。它能拒绝中英文混写等情况，不能判断拉丁字母组成的文字是否真是英文。评论和摘要由成员及 agent 按规范撰写，不由此检查自动翻译或验证。编辑 PR 标题/正文会重新运行 CI。

## 3. 自动合并的条件与执行方式

[auto_merge.py](../.github/scripts/auto_merge.py)在每次 RoadGuard CI 完成后检查当前所有面向 `main` 的开放 PR，也可从 Actions 手动触发。满足以下条件才执行：

- 非草稿、来源为本仓库，作者当前具有 write、maintain 或 admin 权限。
- 英文标题与正文符合字符检查；不存在尚未解决的 changes requested。无需任何 APPROVED review。
- 不修改 `.github/` 下的控制文件，包含重命名移入/移出。控制文件由 agent 审查并在 CI 通过后合并，已获项目发起人持续授权，不增加人工批准步骤。
- 当前 PR head 对应的最新 RoadGuard CI 运行成功；核验受信工作流 ID、PR 关联、仓库、SHA、运行 attempt 和四个 job，不能使用旧提交或旧失败前的绿色结果。
- 分支包含当前 `main`，GitHub 报告可合并且无冲突；临近合并再次读取 PR、head、main、review 和 CI，并用 head SHA 作为合并 API 的条件。

工作流只从 `main` 检出检查脚本，不运行 PR 中的代码、不下载 PR 产物。写权限仅给合并 job，使用 GitHub 自带的短期 `GITHUB_TOKEN`，不新增 PAT 或外部密钥。所有合并运行串行执行；主分支更新后其他落后分支须自行同步，再跑 CI。

`GITHUB_TOKEN` 产生的合并不会自动触发普通 push 工作流，因此脚本在成功合并后显式 dispatch `ci.yml` 的 `main` 运行。若合并已完成而 dispatch 失败，Actions 会明确报错并给出合并 SHA；agent 需重试 main CI。不会假报完整交付成功，也不回滚已合并提交。[GitHub token 触发规则](https://docs.github.com/en/actions/concepts/security/github_token)

看到 PR 没有自动合并时，先查看 RoadGuard Auto Merge 的日志：修正英文描述、转为 Ready、修复失败测试、同步 `main` 或处理已提出的问题后重试。不要靠手动跳过失败检查合并。

## 4. A/B/C 后续如何接入真实测试

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

## 5. 当前套餐的限制

2026-10-12 查询此私有仓库时，GitHub 的分支保护和 rulesets 接口均返回：需要升级 GitHub Pro 或变更仓库可见性。仓库继续保持私有，不因设置 CI 改为公开。

- 当前流程：功能分支 → 英文 PR → 自动 CI → 独立 Actions 核对并合并 → main CI；无需人工批准。
- 原生 auto-merge 仍未启用，当前使用项目维护的 Actions 实现；无需为了这个流程升级套餐。
- 当前套餐无法强制阻止有写权限的成员直接推 `main` 或手动绕过检查。GitHub 合并 API 仅支持 head SHA 条件，无法原子锁定 main；临近合并再次检查会缩小窗口，但不能阻止外部账号同时直接更新 main。因此所有成员均须遵守分支与 PR 流程。

如果以后账户获得支持私有仓库保护的套餐，A 可对 `main` 启用：必须 PR、要求 `CI` 检查且分支保持最新、处理未解决的问题、禁止强制推送和删除、管理员也遵守；所需人工批准数量保持为零。迁移到原生自动合并时停用本工作流，避免双重控制。此次没有开通付费套餐或更改仓库可见性。

## 6. 费用与运行限制

GitHub Free 的 Actions 标准 runner 每月含 2,000 分钟，按账户共享；私有仓库的原生自动合并和分支保护需要 Pro 等支持的套餐。这里采用标准 Linux runner，不使用付费的大型 runner、不保留构建产物、不启用依赖缓存，单个任务设置 2～10 分钟超时，并取消同一 PR 的旧运行。

额度内无需额外付费；超过额度是否停止或产生费用，取决于账号付款方式及预算设置。此次没有查看剩余额度或更改账单/预算，不能保证账户其他项目不会耗尽额度。

官方参考：[套餐](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)、[Actions 计费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[自动合并](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request)。
