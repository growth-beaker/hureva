"""Slack delivery (§7.3, §13.7).

Per-person routing runs inside the library: it resolves the handle to a Slack
user via ``users.lookupByEmail`` when given an email, else posts directly to a
channel/handle, then ``chat.postMessage``. The ``slackapi/slack-github-action``
marketplace action is the simpler drop-in when a team only posts to one channel;
this sender is the per-person path (§13.7).

The Slack SDK is imported lazily so the core library has no hard dependency on it
— a team that only sends email never needs it installed.
"""

from __future__ import annotations

from ..events import Notification
from . import Sender


class SlackSender(Sender):
    channel = "slack"

    def __init__(self, token: str, client=None):
        self._token = token
        # Injectable for tests; real client built lazily to avoid a hard dep.
        self._client = client

    def _get_client(self):
        if self._client is None:
            from slack_sdk import WebClient  # lazy import

            self._client = WebClient(token=self._token)
        return self._client

    def _resolve_user(self, handle: str) -> str:
        """Turn a roster handle into a Slack conversation target.

        ``@name`` / ``#channel`` handles post as-is. An email resolves to a user
        id via ``users.lookupByEmail`` so DMs key off the roster's email (§7.3).
        """
        if handle.startswith(("#", "@", "C", "U", "D")):
            return handle
        if "@" in handle:
            client = self._get_client()
            resp = client.users_lookupByEmail(email=handle)
            return resp["user"]["id"]
        return handle

    def send(self, notification: Notification) -> None:
        client = self._get_client()
        target = self._resolve_user(notification.handle)
        text = f"*{notification.subject}*\n{notification.body}"
        client.chat_postMessage(channel=target, text=text)
