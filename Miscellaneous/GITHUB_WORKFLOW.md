# RoadGuard branches, pull requests and CI

Workflow record updated: 2026-10-12; English translation: 2026-10-19. This guide describes the committed CI configuration and its limits. Each run's result is recorded in GitHub Actions. Account-plan observations below are dated records, not a fresh billing check.

## 1. Daily workflow for members

1. Accept the repository invitation and clone it using your own GitHub account. Read root [AGENTS.md](../AGENTS.md) first.
2. With no unresolved local changes, update `main` and create a short-lived branch for the task.
3. Complete the implementation, relevant tests and documentation, then commit and push your branch.
4. Open a Pull Request targeting `main` and complete the English PR template. Use English for the title, body, summaries, comments and merge description. Use a Draft PR when work is not ready to merge.
5. Opening a PR or pushing further commits to its branch automatically runs RoadGuard CI. Inspect Checks for the latest commit.
6. Under the project initiator's explicit authorization, RoadGuard Auto Merge squash-merges ordinary ready PRs once the conditions below pass. No human review, approval or additional merge click is required. If the branch is behind `main` or has conflicts, synchronize and resolve them on the feature branch, then push for new checks.
7. After a bot merge, the workflow explicitly starts CI on `main` to verify the merged version. Account/agent merges trigger it through the push event. If it fails, the responsible member opens a fix PR; there is no automatic rollback. An agent reviews PRs touching `.github/` and merges after self-checks and CI verification, without human confirmation.

Example, only when there are no pending local changes:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/b-greedy-planner
# Complete the task and local verification, then stage specific files.
git add <files-changed-for-this-task>
git commit -m "feat(routing): add greedy planner"
git push -u origin feature/b-greedy-planner
```

On GitHub, select **Pull requests → New pull request**, then choose the feature branch → `main`. Pushing a feature branch with no PR does not start CI, avoiding duplicate usage. Every update after PR creation reruns checks. A workflow can also be started manually from Actions.

Do not use force-push to resolve synchronization failures, include another member's changes in your commit, or push routine development directly to `main`. If `main` changes while the PR is waiting, synchronize and wait for fresh checks. The recorded account plan does not enforce an up-to-date-branch protection rule.

## 2. What the automatic checks do

Configuration: [ci.yml](../.github/workflows/ci.yml). The check workflow has only `contents: read` permission. The separate [auto-merge workflow](../.github/workflows/auto-merge.yml) verifies merge conditions after CI completes. Neither workflow deploys the application.

| GitHub check | Behaviour |
| --- | --- |
| Repository checks | Validates course folders and policy files, JSON, four-crew/Jurong defaults, local Markdown file links, unresolved merge markers, Python syntax and selected accidentally committed local artifacts. Runs CI-script regression tests and checks English PR titles/bodies. |
| Python tests | When Python code exists in backend, model, experiments or shared tests, installs declared CI dependencies and runs pytest. Skipped only when the corresponding code is absent. |
| Frontend checks | When frontend code or package.json exists, runs npm ci, lint, test:ci and build. Skipped only when no frontend implementation exists. |
| CI | Aggregates results. Repository checks and all checks for present modules must pass. Failures, cancellation and unexpected skips cannot produce a passing result. |

The original 12 October setup already contained backend foundations and shared schemas, making Python tests mandatory; the frontend was not yet implemented at that checkpoint. Both modules are now present and both application checks are required. A skip means the corresponding module is absent, not that its tests passed. Checks cannot prove all logic correct: contributors and agents must still verify their changes. Human review is not a PR gate. Markdown validation checks local file targets, not remote pages or heading anchors.

Since 14 October, Repository checks allow the single explicitly approved deployment weight, `SystemCode/backend/roadguard/model/roadguard-yolo11s-single-v1.pt`, to be committed with code. They check its fixed size, SHA-256 and consistency with the default model manifest. Missing/corrupt files, incorrect versions and Git LFS pointers fail. The exception does not permit other weights; forcibly tracked Dataset files also fail. CI reads bytes to calculate the hash without loading or executing the weight. Real inference remains a local acceptance check. An approved deployment-weight update must synchronize the manifest and validation constants.

The English check requires nonempty titles/bodies and allows Latin letters, digits and punctuation, including Markdown, URLs, accented Latin letters and emoji. It rejects mixed Chinese/English text, but cannot determine whether Latin-letter text is linguistically English. Members and agents must follow the policy for comments and summaries; this check does not translate or validate those fields. Editing a PR title/body reruns CI.

## 3. Auto-merge conditions and execution

[auto_merge.py](../.github/scripts/auto_merge.py) checks all open PRs targeting `main` after each RoadGuard CI completion; it can also be started manually from Actions. It merges only when all conditions hold:

- The PR is not a draft, comes from this repository, and its author currently has write, maintain or admin permission.
- The English title/body pass the character check, and no unresolved changes-requested review remains. No APPROVED review is required.
- The PR does not change `.github/` control files, including renames into or out of that directory. An agent reviews those changes and merges after CI passes under the initiator's standing authorization; no extra human approval is required.
- The latest RoadGuard CI run for the current PR head succeeds. The script verifies the trusted workflow ID, PR association, repository, SHA, run attempt and all four jobs. A green result for an older commit or an earlier failed attempt is insufficient.
- The branch contains current `main`, and GitHub reports it mergeable without conflicts. Immediately before merging, the script rereads the PR, head, main, reviews and CI, then uses the head SHA as the merge API precondition.

The workflow checks out its control script only from `main`; it does not execute PR code or download PR artifacts. Only the merge job receives write permission, using GitHub's short-lived `GITHUB_TOKEN`; no new PAT or external secret is added. Merge runs execute serially. Once main advances, other branches that fall behind must synchronize and rerun CI.

A merge performed with `GITHUB_TOKEN` does not automatically start an ordinary push workflow, so the script explicitly dispatches `ci.yml` on `main` after merging. If dispatch fails after a successful merge, Actions reports the failure and merge SHA. The agent must retry main CI. It must neither claim complete delivery nor roll back the merged commit automatically. See [GitHub token trigger rules](https://docs.github.com/en/actions/concepts/security/github_token).

If a PR is not automatically merged, inspect RoadGuard Auto Merge logs first. Correct the English description, mark the PR ready, fix failing tests, synchronize `main` or address outstanding review issues, then retry. Do not manually bypass failed checks.

## 4. Integrating module tests

CI uses Python 3.11, Node 22, npm and a standard Ubuntu runner. Use those versions when establishing the development environment, or coordinate CI and development-guide updates in the same PR.

**A/B: Python modules**

- When adding the first business Python files, include `SystemCode/backend/requirements-ci.txt` with pinned pytest and required test dependencies. References to other requirements files must work when installed from the repository root.
- Place unit/integration tests in `SystemCode/tests/`, organized by module, using pytest's `test_*.py` or `*_test.py` names.
- CI runs `python -m pip install -r SystemCode/backend/requirements-ci.txt`, then `python -m pytest SystemCode/tests -q` from the repository root. Imports must work through reproducible installation or project configuration, without personal machine paths.
- Missing dependency declarations or test files fail; collecting zero tests also fails. Ordinary PR checks must not train models, download the complete dataset or call paid APIs. Use small fixtures and replaceable services to verify logic.

**C: frontend**

- Commit `SystemCode/frontend/package.json` and its matching `package-lock.json`; use npm consistently.
- Provide executable `lint`, `test:ci` and `build` scripts, plus at least one `*.test.*` or `*.spec.*` test file.
- `test:ci` must exit after one run and return a nonzero status for failures or no tests. Do not use echo, `--passWithNoTests` or ignored exit codes to fabricate success.
- Do not inject real service keys. Use explicit test doubles for external models, travel services and GPT requests.

Run CI-infrastructure checks locally from the repository root:

```bash
python -m unittest discover -s .github/scripts -p "test_*.py" -v
python .github/scripts/check_repository.py
```

## 5. Recorded account-plan limitations

On 12 October 2026, branch-protection and ruleset requests for this private repository returned a requirement to upgrade to GitHub Pro or change repository visibility. The repository remains private; configuring CI did not make it public.

- The workflow is feature branch → English PR → automatic CI → independent Actions verification and merge → main CI, without human approval.
- Native auto-merge was not enabled. The project-maintained Actions implementation provides the agreed flow without upgrading the plan.
- The recorded plan cannot enforce a ban on members with write permission pushing directly to `main` or manually bypassing checks. GitHub's merge API supports a head-SHA condition but cannot atomically lock main. A final recheck narrows the race window but cannot stop an external account from updating main concurrently. Every member must follow the branch/PR process.

If the account later gains private-repository protection, A can require PRs, a passing `CI` check on an up-to-date branch, resolution of outstanding issues, no force-push/deletion, and administrator compliance. Keep required human approvals at zero. Disable the custom workflow when moving to native auto-merge to avoid duplicate control. This setup did not activate a paid plan or change repository visibility.

## 6. Recorded costs and execution limits

The 12 October setup record notes 2,000 included standard-runner minutes per month for GitHub Free, shared across the account, and a supported paid plan for native auto-merge/branch protection on private repositories. This workflow uses standard Linux runners, no paid larger runners, no retained build artifacts and no dependency cache. Jobs have two-to-ten-minute timeouts, and newer PR runs cancel older ones.

Included usage incurs no additional charge. Whether exceeding the allowance stops runs or incurs charges depends on the account's payment method and budget settings. Remaining usage and billing/budget settings were not inspected or changed. Other repositories may consume the shared allowance.

Official references: [plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), and [auto-merge](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request).
