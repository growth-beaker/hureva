import pytest

from hureva.events import Event, Notification
from hureva.senders import DryRunSender, MultiSender, build_sender
from hureva.senders.email import SmtpSender
from hureva.senders.slack import SlackSender


def _note(channel="slack", handle="@x"):
    return Notification(
        event=Event.ready_for_review, slug="widget", recipient="x",
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
