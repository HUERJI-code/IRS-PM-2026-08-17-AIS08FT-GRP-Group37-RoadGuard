"""Metadata-only auto-merge checks; all network and mutations are fake."""

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from auto_merge import APIError, AutoMerger, GitHubClient, NoRedirect, main


REPO = "owner/RoadGuard"
HEAD = "a" * 40
BASE = "b" * 40
MERGED = "c" * 40


class FakeClient:
    def __init__(self):
        self.calls = []
        self.pr = {
            "number": 1, "state": "open", "draft": False, "changed_files": 1,
            "title": "Add backend infrastructure", "body": "Add shared configuration and tests.",
            "base": {"ref": "main", "sha": BASE, "repo": {"full_name": REPO}},
            "head": {"sha": HEAD, "repo": {"full_name": REPO}},
            "user": {"login": "owner"}, "mergeable": True, "mergeable_state": "clean",
        }
        self.workflow = {"id": 99, "path": ".github/workflows/ci.yml", "name": "RoadGuard CI"}
        self.runs = [{"id": 100, "workflow_id": 99, "event": "pull_request",
                      "path": ".github/workflows/ci.yml", "head_sha": HEAD,
                      "head_repository": {"full_name": REPO}, "pull_requests": [{"number": 1}],
                      "created_at": "2026-10-12T10:00:00Z", "run_attempt": 2,
                      "status": "completed", "conclusion": "success"}]
        self.jobs = [{"name": name, "run_id": 100, "status": "completed", "conclusion": result}
                     for name, result in (("Repository checks", "success"), ("Python tests", "success"),
                                          ("Frontend checks", "skipped"), ("CI", "success"))]
        self.files = [{"filename": "SystemCode/backend/roadguard/main.py"}]
        self.reviews = []
        self.permission = "write"
        self.comparison = {"behind_by": 0, "status": "ahead"}
        self.base_sha = BASE
        self.merge_result = {"merged": True, "sha": MERGED}
        self.dispatch_fails = False
        self.fresh_change = None
        self.pr_reads = 0
        self.base_reads = 0
        self.base_change = False
        self.new_ci_on_recheck = False
        self.run_reads = 0
        self.new_review_on_recheck = False
        self.review_reads = 0

    def request(self, method, path, body=None):
        self.calls.append((method, path, deepcopy(body)))
        parsed = urlsplit(path)
        route = parsed.path.removeprefix("/repos/" + REPO)
        query = parse_qs(parsed.query)
        page = int(query.get("page", [1])[0])
        if route == "/actions/workflows/ci.yml" and method == "GET":
            return deepcopy(self.workflow)
        if route == "/pulls" and method == "GET":
            return [deepcopy(self.pr)] if page == 1 else []
        if route == "/pulls/1" and method == "GET":
            self.pr_reads += 1
            result = deepcopy(self.pr)
            if self.pr_reads > 1 and self.fresh_change:
                self.fresh_change(result)
            return result
        if route.startswith("/collaborators/"):
            return {"permission": self.permission}
        if route == "/pulls/1/files":
            return deepcopy(self.files[(page - 1) * 100:page * 100])
        if route == "/pulls/1/reviews":
            self.review_reads += 1
            if self.new_review_on_recheck and self.review_reads > 1:
                return [{"id": 22, "user": {"login": "reviewer"}, "state": "CHANGES_REQUESTED",
                         "submitted_at": "2026-10-12T10:00:00Z"}]
            return deepcopy(self.reviews)
        if route == "/actions/workflows/99/runs":
            self.run_reads += 1
            result = deepcopy(self.runs)
            if self.new_ci_on_recheck and self.run_reads > 1:
                result[-1]["conclusion"] = "failure"
            return {"total_count": len(result), "workflow_runs": result}
        if route == "/actions/runs/100/attempts/2/jobs":
            return {"total_count": len(self.jobs), "jobs": deepcopy(self.jobs)}
        if route == "/git/ref/heads/main":
            self.base_reads += 1
            sha = "d" * 40 if self.base_change and self.base_reads > 1 else self.base_sha
            return {"object": {"sha": sha}}
        if route == f"/compare/{BASE}...{HEAD}":
            return deepcopy(self.comparison)
        if route == "/pulls/1/merge" and method == "PUT":
            return deepcopy(self.merge_result)
        if route == "/actions/workflows/ci.yml/dispatches" and method == "POST":
            if self.dispatch_fails:
                raise APIError("GitHub API request failed (HTTP 403).")
            return {}
        raise AssertionError(f"Unexpected fake request: {method} {route}")


class AutoMergeTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.sleep_patch = patch("auto_merge.sleep")
        self.sleep = self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)

    def attempt(self):
        with redirect_stdout(io.StringIO()):
            return AutoMerger(self.client, REPO).try_merge(1)

    def assert_skips(self):
        self.assertTrue(self.attempt().startswith("Skipped:"))
        self.assertFalse(any(method in {"PUT", "POST"} for method, _, _ in self.client.calls))

    def test_green_current_head_merges_and_dispatches_main_with_expected_sha(self):
        self.assertTrue(self.attempt().startswith("Merged:"))
        writes = [call for call in self.client.calls if call[0] in {"PUT", "POST"}]
        self.assertEqual([call[0] for call in writes], ["PUT", "POST"])
        self.assertEqual(writes[0][2], {"sha": HEAD, "merge_method": "squash",
                                       "commit_title": self.client.pr["title"], "commit_message": self.client.pr["body"]})
        self.assertEqual(writes[1][2], {"ref": "main"})
        self.assertTrue(any("/attempts/2/jobs" in path for _, path, _ in self.client.calls))

    def test_draft_fork_closed_wrong_base_and_nonenglish_are_skipped(self):
        changes = [lambda p: p.update(draft=True), lambda p: p.update(state="closed"),
                   lambda p: p["head"].update(repo={"full_name": "stranger/fork"}),
                   lambda p: p["base"].update(ref="other"), lambda p: p.update(title="中文标题"),
                   lambda p: p.update(body=""), lambda p: p.update(title=""),
                   lambda p: p.update(body="Fix the issue 中文"), lambda p: p["head"].update(repo=None)]
        for change in changes:
            with self.subTest(change=change):
                self.client = FakeClient()
                change(self.client.pr)
                self.assert_skips()

    def test_author_must_have_write_permission(self):
        for permission in ("read", "triage", "none"):
            with self.subTest(permission=permission):
                self.client = FakeClient()
                self.client.permission = permission
                self.assert_skips()
        for permission in ("write", "maintain", "admin"):
            self.client = FakeClient()
            self.client.permission = permission
            self.assertTrue(self.attempt().startswith("Merged:"))

    def test_invalid_author_login_never_enters_url(self):
        self.client.pr["user"]["login"] = "owner/../../secret"
        self.assert_skips()
        self.assertFalse(any("collaborators" in path for _, path, _ in self.client.calls))

    def test_control_changes_and_renames_are_skipped(self):
        for item in ({"filename": ".github/workflows/ci.yml"},
                     {"filename": "moved.py", "previous_filename": ".github/scripts/auto_merge.py"},
                     {"filename": ".github/scripts/new.py", "previous_filename": "outside.py"}):
            with self.subTest(item=item):
                self.client = FakeClient()
                self.client.files = [item]
                self.assert_skips()

    def test_all_file_pages_are_checked(self):
        self.client.files = [{"filename": f"docs/{number}.md"} for number in range(100)]
        self.client.files.append({"filename": ".github/new.yml"})
        self.client.pr["changed_files"] = 101
        self.assert_skips()
        self.assertTrue(any("files?" in path and "page=2" in path for _, path, _ in self.client.calls))

    def test_incomplete_file_metadata_is_skipped(self):
        self.client.pr["changed_files"] = 3001
        self.assert_skips()

    def test_unresolved_changes_requested_blocks_merge(self):
        self.client.reviews = [{"id": 10, "user": {"login": "reviewer"}, "state": "CHANGES_REQUESTED",
                                "submitted_at": "2026-10-12T09:00:00Z"}]
        self.assert_skips()

    def test_latest_approval_or_dismissal_clears_request(self):
        for state in ("APPROVED", "DISMISSED"):
            self.client = FakeClient()
            self.client.reviews = [
                {"id": 10, "user": {"login": "reviewer"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-12T09:00:00Z"},
                {"id": 11, "user": {"login": "reviewer"}, "state": state, "submitted_at": "2026-10-12T10:00:00Z"},
            ]
            self.assertTrue(self.attempt().startswith("Merged:"))

    def test_later_comment_does_not_clear_request_and_other_reviewer_cannot_clear_it(self):
        self.client.reviews = [
            {"id": 10, "user": {"login": "one"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-10-12T09:00:00Z"},
            {"id": 11, "user": {"login": "one"}, "state": "COMMENTED", "submitted_at": "2026-10-12T10:00:00Z"},
            {"id": 12, "user": {"login": "two"}, "state": "APPROVED", "submitted_at": "2026-10-12T11:00:00Z"},
        ]
        self.assert_skips()

    def test_missing_mismatched_or_unlinked_ci_is_skipped(self):
        changes = [lambda r: r.update(head_sha="d" * 40), lambda r: r.update(workflow_id=88),
                   lambda r: r.update(event="push"), lambda r: r.update(path=".github/workflows/fake.yml"),
                   lambda r: r.update(head_repository={"full_name": "other/fork"}),
                   lambda r: r.update(pull_requests=[]), lambda r: r.update(pull_requests=[{"number": 2}])]
        for change in changes:
            self.client = FakeClient()
            change(self.client.runs[0])
            self.assert_skips()
        self.client = FakeClient()
        self.client.runs = []
        self.assert_skips()

    def test_failed_pending_and_cancelled_latest_runs_are_skipped(self):
        for status, conclusion in (("queued", None), ("in_progress", None), ("completed", "failure"),
                                   ("completed", "cancelled"), ("completed", "neutral")):
            self.client = FakeClient()
            self.client.runs[0].update(status=status, conclusion=conclusion)
            self.assert_skips()

    def test_older_green_cannot_override_newer_failed_or_pending_run(self):
        for status, conclusion in (("completed", "failure"), ("queued", None)):
            self.client = FakeClient()
            newer = deepcopy(self.client.runs[0])
            newer.update(id=101, created_at="2026-10-12T11:00:00Z", status=status, conclusion=conclusion)
            self.client.runs.append(newer)
            self.assert_skips()

    def test_missing_failed_pending_duplicate_and_wrong_run_jobs_are_skipped(self):
        changes = [lambda jobs: jobs.pop(), lambda jobs: jobs[1].update(conclusion="failure"),
                   lambda jobs: jobs[1].update(status="in_progress"), lambda jobs: jobs[0].update(conclusion="skipped"),
                   lambda jobs: jobs[0].update(run_id=999), lambda jobs: jobs.append(deepcopy(jobs[0]))]
        for change in changes:
            self.client = FakeClient()
            change(self.client.jobs)
            self.assert_skips()

    def test_behind_or_conflicting_comparison_is_skipped(self):
        for comparison in ({"behind_by": 1, "status": "diverged"}, {"behind_by": 1, "status": "behind"}, {}):
            self.client = FakeClient()
            self.client.comparison = comparison
            self.assert_skips()

    def test_stale_head_base_metadata_and_mergeability_are_skipped(self):
        changes = [lambda p: p["head"].update(sha="d" * 40), lambda p: p["base"].update(sha="d" * 40),
                   lambda p: p.update(mergeable=False), lambda p: p.update(mergeable=None),
                   lambda p: p.update(mergeable_state="dirty"), lambda p: p.update(mergeable_state="unstable"),
                   lambda p: p.update(title="Another English title"), lambda p: p.update(body="Changed body."),
                   lambda p: p.update(draft=True)]
        for change in changes:
            self.client = FakeClient()
            self.client.fresh_change = change
            self.assert_skips()

    def test_fresh_main_review_and_ci_changes_block_merge(self):
        for setting in ("base_change", "new_review_on_recheck", "new_ci_on_recheck"):
            self.client = FakeClient()
            setattr(self.client, setting, True)
            self.assert_skips()

    def test_unknown_mergeability_retries_then_merges_when_clean(self):
        def eventually_clean(pr):
            if self.client.pr_reads < 4:
                pr["mergeable"] = None

        self.client.fresh_change = eventually_clean
        self.assertTrue(self.attempt().startswith("Merged:"))
        self.assertEqual(self.client.pr_reads, 4)
        self.assertEqual(self.sleep.call_count, 2)
        self.sleep.assert_called_with(2)

    def test_unknown_mergeability_has_bounded_retries_and_no_merge(self):
        self.client.fresh_change = lambda pr: pr.update(mergeable=None)
        self.assert_skips()
        self.assertEqual(self.client.pr_reads, 4)
        self.assertEqual(self.sleep.call_count, 2)

    def test_head_change_during_unknown_mergeability_retry_is_rejected(self):
        def changed_head(pr):
            if self.client.pr_reads == 2:
                pr["mergeable"] = None
            else:
                pr["head"]["sha"] = "d" * 40

        self.client.fresh_change = changed_head
        self.assert_skips()
        self.assertEqual(self.client.pr_reads, 3)
        self.sleep.assert_called_once_with(2)

    def test_known_conflict_does_not_retry(self):
        self.client.fresh_change = lambda pr: pr.update(mergeable=False)
        self.assert_skips()
        self.assertEqual(self.client.pr_reads, 2)
        self.sleep.assert_not_called()

    def test_false_merge_response_never_dispatches(self):
        self.client.merge_result = {"merged": False, "message": "untrusted secret"}
        with self.assertRaises(APIError) as error:
            self.attempt()
        self.assertNotIn("secret", str(error.exception))
        self.assertFalse(any(method == "POST" for method, _, _ in self.client.calls))

    def test_dispatch_failure_reports_committed_sha_and_fails_without_rollback(self):
        self.client.dispatch_fails = True
        with self.assertRaises(APIError) as error:
            self.attempt()
        self.assertIn(MERGED, str(error.exception))
        self.assertIn("main CI dispatch failed", str(error.exception))
        self.assertEqual([method for method, _, _ in self.client.calls if method != "GET"], ["PUT", "POST"])

    def test_main_scans_open_prs_and_returns_failure_for_dispatch_error(self):
        for fails in (False, True):
            self.client = FakeClient()
            self.client.dispatch_fails = fails
            with patch.dict(os.environ, {"GITHUB_TOKEN": "secret-token", "GITHUB_REPOSITORY": REPO}), \
                    patch("auto_merge.GitHubClient", return_value=self.client), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(), int(fails))

    def test_untrusted_workflow_identity_is_rejected(self):
        self.client.workflow["path"] = ".github/workflows/fake.yml"
        with self.assertRaises(APIError):
            self.attempt()


class TransportTests(unittest.TestCase):
    def test_http_and_network_errors_are_sanitized(self):
        for failure in (HTTPError("https://secret", 403, "secret-token", {}, None), URLError("secret-token")):
            client = GitHubClient("secret-token")
            with patch.object(client._opener, "open", side_effect=failure):
                with self.assertRaises(APIError) as error:
                    client.request("GET", "/repos/owner/repo/pulls")
                self.assertNotIn("secret", str(error.exception))

    def test_fixed_origin_token_header_and_timeout(self):
        client = GitHubClient("secret-token")
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok":true}'
        with patch.object(client._opener, "open", return_value=response) as open_request:
            self.assertEqual(client.request("GET", "/repos/owner/repo/pulls"), {"ok": True})
            request = open_request.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.github.com/repos/owner/repo/pulls")
            self.assertEqual(request.headers["Authorization"], "Bearer secret-token")
            self.assertEqual(open_request.call_args.kwargs["timeout"], 30)

    def test_redirects_and_external_paths_are_rejected(self):
        with self.assertRaises(APIError):
            NoRedirect().redirect_request(None, None, 302, "moved", {}, "https://evil.test")
        with self.assertRaises(APIError):
            GitHubClient("token").request("GET", "https://evil.test")

    def test_missing_env_and_malformed_metadata_fail_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(), 1)
            self.assertIn("required", output.getvalue())
        with self.assertRaises(APIError):
            AutoMerger(FakeClient(), "../secret/repo")


if __name__ == "__main__":
    unittest.main()
