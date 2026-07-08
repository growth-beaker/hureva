import urllib.error

import pytest

from hureva.events import Event, Notification
from hureva.senders import DryRunSender, MultiSender, build_sender
from hureva.senders.email import SmtpSender
from hureva.senders.github import GitHubSender
from hureva.senders.slack import SlackSender


def _note(channel="slack", handle="@x", event=Event.ready_for_review, slug="widget"):
    return Notification(
        event=event, slug=slug, recipient="x",
        channel=channel, handle=handle, subject="s", body="b",
    )


def test_dry_run_records_all_channels():
    dry = DryRunSender()
    ms = MultiSender({"slack": dry, "email": dry}, fallback=dry)
    ms.send(_note("slack"))
    ms.send(_note("email", "x@y.com"))
    assert len(dry.sent) == 2


def test_multisender_unknown_channel_raises():
    ms = MultiSender({})
    with pytest.raises(LookupError):
        ms.send(_note("carrier-pigeon"))


def test_build_sender_dry_run_needs_no_creds():
    ms = build_sender(dry_run=True, env={})
    ms.send(_note("slack"))
    ms.send(_note("email", "x@y.com"))  # both go to the dry sender


def test_build_sender_enables_only_configured_channels():
    ms = build_sender(env={"SLACK_BOT_TOKEN": "xoxb-1"})
    assert "slack" in ms._senders
    assert "email" not in ms._senders


def test_build_sender_email_from_env():
    ms = build_sender(env={"SMTP_HOST": "smtp.acme.com", "SMTP_PORT": "2525"})
    assert isinstance(ms._senders["email"], SmtpSender)
    assert ms._senders["email"].port == 2525


def test_build_sender_enables_github_from_env():
    ms = build_sender(env={"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"})
    assert isinstance(ms._senders["github"], GitHubSender)


def test_build_sender_dry_run_handles_github():
    ms = build_sender(dry_run=True, env={})
    ms.send(_note("github", "octocat"))  # no error, recorded by the dry sender


class _FakeApi:
    """Records GitHub API calls and returns canned responses."""

    def __init__(self, existing_pr=None, fail_reviewer=False, default_branch="main"):
        self.calls = []
        self._existing = existing_pr
        self._fail_reviewer = fail_reviewer
        self._default_branch = default_branch

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and "/pulls?" in path:
            return [{"number": self._existing}] if self._existing else []
        if method == "GET" and "/pulls" not in path:   # GET /repos/{owner}/{repo}
            return {"default_branch": self._default_branch}
        if method == "POST" and path.endswith("/pulls"):
            return {"number": 42}
        if method == "POST" and path.endswith("/requested_reviewers"):
            if self._fail_reviewer:
                raise urllib.error.HTTPError(path, 422, "unprocessable", {}, None)
            return {}
        return {}

    def paths(self):
        return [(m, p.split("?")[0]) for m, p, _ in self.calls]


def test_github_opens_pr_and_requests_reviewer():
    api = _FakeApi()
    GitHubSender("tok", "growth-beaker/hureva", api=api).send(_note("github", "elena"))
    assert ("POST", "/repos/growth-beaker/hureva/pulls") in api.paths()          # created PR
    assert any(p.endswith("/requested_reviewers") for _, p in api.paths())       # requested


def test_github_reuses_existing_pr():
    api = _FakeApi(existing_pr=7)
    GitHubSender("t", "o/r", api=api).send(_note("github", "a"))
    assert not any(m == "POST" and p.endswith("/pulls") for m, p in api.paths())


def test_github_targets_repo_default_branch():
    api = _FakeApi(default_branch="trunk")
    GitHubSender("t", "o/r", api=api).send(_note("github", "a"))
    create = next(b for m, p, b in api.calls if m == "POST" and p.endswith("/pulls"))
    assert create["base"] == "trunk"


def test_github_explicit_base_skips_lookup():
    api = _FakeApi(default_branch="trunk")
    GitHubSender("t", "o/r", base_branch="release", api=api).send(_note("github", "a"))
    create = next(b for m, p, b in api.calls if m == "POST" and p.endswith("/pulls"))
    assert create["base"] == "release"
    assert not any(m == "GET" and "/pulls" not in p for m, p, _ in api.calls)  # no repo GET


def test_github_falls_back_to_comment_when_request_rejected():
    api = _FakeApi(fail_reviewer=True)
    GitHubSender("t", "o/r", api=api).send(_note("github", "sam"))
    assert any("/comments" in p for _, p in api.paths())


def test_github_owner_event_comments_not_requests():
    api = _FakeApi()
    GitHubSender("t", "o/r", api=api).send(_note("github", "chris", event=Event.approved))
    assert any("/comments" in p for _, p in api.paths())
    assert not any(p.endswith("/requested_reviewers") for _, p in api.paths())


class _FakeSlackClient:
    def __init__(self):
        self.posted = []

    def users_lookupByEmail(self, email):
        return {"user": {"id": "U123"}}

    def chat_postMessage(self, channel, text):
        self.posted.append((channel, text))


def test_slack_sender_posts_to_handle():
    client = _FakeSlackClient()
    s = SlackSender(token="t", client=client)
    s.send(_note("slack", "#qa"))
    assert client.posted[0][0] == "#qa"
    assert "*s*" in client.posted[0][1]  # subject bolded, body appended


def test_slack_sender_resolves_email_to_user_id():
    client = _FakeSlackClient()
    s = SlackSender(token="t", client=client)
    s.send(_note("slack", "person@acme.com"))
    assert client.posted[0][0] == "U123"


def test_smtp_sender_uses_injected_transport():
    captured = []
    s = SmtpSender(host="h", transport=captured.append)
    s.send(_note("email", "person@acme.com"))
    msg = captured[0]
    assert msg["To"] == "person@acme.com"
    assert msg["Subject"] == "s"
    assert "b" in msg.get_content()
