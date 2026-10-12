"""Merge eligible PRs using GitHub metadata; never load or execute PR content."""

import json
import os
import re
import sys
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pr_language import validate_english


class APIError(RuntimeError):
    """A fixed public diagnostic, without response bodies, URLs or credentials."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise APIError("GitHub API redirect rejected.")


class GitHubClient:
    def __init__(self, token):
        self._token = token
        self._opener = build_opener(NoRedirect())

    def request(self, method, path, body=None):
        if not path.startswith("/repos/") or "\r" in path or "\n" in path:
            raise APIError("Invalid GitHub API request.")
        request = Request(
            "https://api.github.com" + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Authorization": "Bearer " + self._token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=30) as response:
                content = response.read()
                return json.loads(content) if content else {}
        except HTTPError as exc:
            raise APIError(f"GitHub API request failed (HTTP {exc.code}).") from None
        except (URLError, OSError, ValueError):
            raise APIError("GitHub API request failed.") from None


class AutoMerger:
    def __init__(self, client, repository):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise APIError("Invalid repository setting.")
        self.client = client
        self.repository = repository
        self.prefix = "/repos/" + repository
        workflow = self.get("/actions/workflows/ci.yml")
        if workflow.get("path") != ".github/workflows/ci.yml" or workflow.get("name") != "RoadGuard CI":
            raise APIError("The trusted CI workflow could not be identified.")
        self.workflow_id = self.identifier(workflow.get("id"))

    @staticmethod
    def identifier(value):
        if type(value) is not int or value <= 0:
            raise APIError("GitHub returned invalid metadata.")
        return value

    def get(self, path):
        return self.client.request("GET", self.prefix + path)

    def pages(self, path, key=None, params=None):
        items = []
        page = 1
        while True:
            query = dict(params or {}, per_page=100, page=page)
            data = self.get(path + "?" + urlencode(query))
            batch = data.get(key) if key else data
            if not isinstance(batch, list):
                raise APIError("GitHub returned invalid list metadata.")
            items.extend(batch)
            if len(batch) < 100:
                if key and data.get("total_count", len(items)) > len(items):
                    raise APIError("GitHub returned incomplete list metadata.")
                return items
            page += 1

    def same_repo(self, repository):
        return isinstance(repository, dict) and str(repository.get("full_name", "")).lower() == self.repository.lower()

    def basic_eligible(self, pr):
        return (
            pr.get("state") == "open" and pr.get("draft") is False
            and pr.get("base", {}).get("ref") == "main"
            and self.same_repo(pr.get("base", {}).get("repo"))
            and self.same_repo(pr.get("head", {}).get("repo"))
            and not validate_english(pr.get("title"), pr.get("body"))
        )

    def authorized_author(self, pr):
        login = pr.get("user", {}).get("login")
        if not isinstance(login, str) or not re.fullmatch(r"[A-Za-z0-9_-]+(?:\[bot\])?", login):
            return False
        permission = self.get("/collaborators/" + quote(login, safe="") + "/permission")
        return permission.get("permission") in {"write", "maintain", "admin"}

    def control_files_unchanged(self, number, pr):
        files = self.pages(f"/pulls/{number}/files")
        if type(pr.get("changed_files")) is not int or len(files) != pr["changed_files"]:
            return False  # Includes GitHub's 3,000-file response limit.
        return all(
            isinstance(item.get("filename"), str)
            and not any(str(item.get(key, "")).startswith(".github/") for key in ("filename", "previous_filename"))
            for item in files
        )

    def reviews_clear(self, number):
        latest = {}
        for review in self.pages(f"/pulls/{number}/reviews"):
            state = review.get("state")
            if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
                continue  # A comment does not resolve a request for changes.
            login = review.get("user", {}).get("login")
            if not login:
                return False
            order = (review.get("submitted_at", ""), self.identifier(review.get("id")))
            if login not in latest or order > latest[login][0]:
                latest[login] = (order, state)
        return all(state != "CHANGES_REQUESTED" for _, state in latest.values())

    def green_ci(self, number, sha):
        runs = self.pages(f"/actions/workflows/{self.workflow_id}/runs", "workflow_runs",
                          {"event": "pull_request", "head_sha": sha})
        matching = [run for run in runs if (
            run.get("workflow_id") == self.workflow_id and run.get("event") == "pull_request"
            and run.get("path", "").split("@")[0] == ".github/workflows/ci.yml"
            and run.get("head_sha") == sha and self.same_repo(run.get("head_repository"))
            and any(link.get("number") == number for link in run.get("pull_requests", []))
        )]
        if not matching:
            return False
        run = max(matching, key=lambda item: (item.get("created_at", ""), self.identifier(item.get("id"))))
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            return False
        run_id, attempt = self.identifier(run.get("id")), self.identifier(run.get("run_attempt"))
        jobs = self.pages(f"/actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs")
        names = {}
        for job in jobs:
            if job.get("run_id") != run_id or job.get("status") != "completed":
                return False
            if job.get("name") in names:
                return False
            names[job.get("name")] = job.get("conclusion")
        required = {"Repository checks", "Python tests", "Frontend checks", "CI"}
        if not required.issubset(names):
            return False
        # Trusted CI aggregate validates which application jobs may be skipped.
        return names["Repository checks"] == names["CI"] == "success" and all(
            names[name] in {"success", "skipped"} for name in ("Python tests", "Frontend checks")
        )

    def main_sha(self):
        sha = self.get("/git/ref/heads/main").get("object", {}).get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise APIError("GitHub returned invalid main metadata.")
        return sha

    def fresh_pull_request(self, number):
        # GitHub computes mergeability asynchronously after a PR metadata request.
        # Retry only unknown results, with a small fixed bound; every guard below
        # still uses the final response and current CI/review/base metadata.
        for attempt in range(3):
            pr = self.get(f"/pulls/{number}")
            if pr.get("mergeable") is not None or attempt == 2:
                return pr
            sleep(2)

    def try_merge(self, number):
        number = self.identifier(number)
        pr = self.get(f"/pulls/{number}")
        if not self.basic_eligible(pr):
            return "Skipped: draft, fork, base or PR language is ineligible."
        if not self.authorized_author(pr):
            return "Skipped: PR author does not have repository write permission."
        if not self.control_files_unchanged(number, pr):
            return "Skipped: repository automation files changed or file metadata is incomplete."
        if not self.reviews_clear(number):
            return "Skipped: an unresolved request for changes exists."
        sha = pr.get("head", {}).get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha) or not self.green_ci(number, sha):
            return "Skipped: latest CI for the current PR head is not fully successful."
        base_sha = self.main_sha()
        comparison = self.get(f"/compare/{base_sha}...{sha}")
        if comparison.get("behind_by") != 0 or comparison.get("status") not in {"ahead", "identical"}:
            return "Skipped: PR branch is behind main or comparison is unavailable."
        fresh = self.fresh_pull_request(number)
        if (
            not self.basic_eligible(fresh) or fresh.get("head", {}).get("sha") != sha
            or fresh.get("title") != pr.get("title") or fresh.get("body") != pr.get("body")
            or fresh.get("user", {}).get("login") != pr.get("user", {}).get("login")
            or fresh.get("mergeable") is not True or fresh.get("mergeable_state") != "clean"
            or fresh.get("base", {}).get("sha") != base_sha
            or not self.reviews_clear(number) or not self.green_ci(number, sha)
            or self.main_sha() != base_sha
        ):
            return "Skipped: PR, base, reviews or CI changed before merging."
        # GitHub supports a head-SHA condition, but this plan cannot atomically lock main.
        result = self.client.request("PUT", self.prefix + f"/pulls/{number}/merge", {
            "sha": sha, "merge_method": "squash",
            "commit_title": fresh["title"], "commit_message": fresh["body"],
        })
        if result.get("merged") is not True:
            raise APIError("GitHub did not merge the eligible pull request.")
        merged_sha = result.get("sha")
        if not isinstance(merged_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", merged_sha):
            raise APIError("PR was merged, but GitHub returned invalid merge metadata.")
        print(f"PR #{number} merged at {merged_sha}.")
        try:
            self.client.request("POST", self.prefix + "/actions/workflows/ci.yml/dispatches", {"ref": "main"})
        except APIError:
            raise APIError(f"PR #{number} was merged at {merged_sha}; main CI dispatch failed. Retry main CI explicitly.") from None
        return "Merged: main CI was explicitly dispatched."


def main():
    token, repository = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY are required.", file=sys.stderr)
        return 1
    try:
        merger = AutoMerger(GitHubClient(token), repository)
        failed = False
        for pr in merger.pages("/pulls", params={"state": "open", "base": "main", "sort": "created", "direction": "asc"}):
            number = merger.identifier(pr.get("number"))
            try:
                print(f"PR #{number}: {merger.try_merge(number)}")
            except APIError as exc:
                failed = True
                print(f"PR #{number}: {exc}", file=sys.stderr)
        return int(failed)
    except (APIError, KeyError, TypeError, AttributeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, APIError) else "GitHub returned invalid metadata."
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
