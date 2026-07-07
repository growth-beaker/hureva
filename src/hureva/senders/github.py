"""GitHub-native delivery (§7.3, §13.6): notify reviewers with no external creds.

The zero-setup channel. Opens (or reuses) a pull request for the spec's
``spec/<slug>`` branch and **requests the recipients as reviewers** — GitHub then
emails and web-notifies them for free, using the workflow's built-in
``GITHUB_TOKEN``. No Slack app, no SMTP.

Reviewers must have access to the repo (be collaborators) to be requested; if
GitHub rejects a request, we fall back to an @mention comment on the PR. Events
that target the owner (e.g. ``approved``) post an @mention comment rather than a
review request.

Standard library only (``urllib``) — no third-party dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..events import Event, Notification
from . import Sender


class GitHubSender(Sender):
    channel = "github"

    def __init__(
        self,
        token: str,
        repository: str,                 # "owner/name" (from $GITHUB_REPOSITORY)
        base_branch: str = "main",
        api_url: str = "https://api.github.com",
        api=None,                        # injectable transport for tests
    ):
        self._token = token
        self._repo = repository
        self._base = base_branch
        self._api_url = api_url.rstrip("/")
        self._api = api or self._http
        self._pr: dict[str, int] = {}    # slug -> PR number (cached within a run)

    # --- HTTP (stdlib) --------------------------------------------------------

    def _http(self, method: str, path: str, body: dict | None = None) -> object:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self._api_url}{path}", data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github+json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode()
        return json.loads(text) if text else {}

    # --- PR find-or-create ----------------------------------------------------

    def _ensure_pr(self, notification: Notification) -> int:
        slug = notification.slug
        if slug in self._pr:
            return self._pr[slug]
        owner = self._repo.split("/")[0]
        head = f"spec/{slug}"
        existing = self._api(
            "GET", f"/repos/{self._repo}/pulls?head={owner}:{head}&state=open"
        )
        if existing:
            number = existing[0]["number"]
        else:
            created = self._api(
                "POST",
                f"/repos/{self._repo}/pulls",
                {
                    "title": notification.subject,
                    "head": head,
                    "base": self._base,
                    "body": notification.body,
                },
            )
            number = created["number"]
        self._pr[slug] = number
        return number

    # --- delivery -------------------------------------------------------------

    def send(self, notification: Notification) -> None:
        pr = self._ensure_pr(notification)
        if notification.event == Event.ready_for_review:
            if not self._request_reviewer(pr, notification.handle):
                self._comment(pr, notification.handle, notification.body)
        else:
            self._comment(pr, notification.handle, notification.body)

    def _request_reviewer(self, pr: int, handle: str) -> bool:
        try:
            self._api(
                "POST",
                f"/repos/{self._repo}/pulls/{pr}/requested_reviewers",
                {"reviewers": [handle.lstrip("@")]},
            )
            return True
        except urllib.error.HTTPError:
            # e.g. 422: not a collaborator, or is the PR author — mention instead.
            return False

    def _comment(self, pr: int, handle: str, body: str) -> None:
        self._api(
            "POST",
            f"/repos/{self._repo}/issues/{pr}/comments",
            {"body": f"@{handle.lstrip('@')}\n\n{body}"},
        )
