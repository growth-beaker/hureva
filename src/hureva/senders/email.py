"""SMTP email delivery (§7.3, §13.6).

The off-the-shelf Action equivalent is ``dawidd6/action-send-mail``; this is the
library-side sender for the same job, reading SMTP creds from the environment so
the workflow only forwards secrets. Email is optional (§13.6): a team with no
SMTP simply never enables this sender (see ``build_sender``).

Uses only the stdlib ``smtplib`` / ``email`` — no third-party dependency.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Optional

from ..events import Notification
from . import Sender


@dataclass
class SmtpSender(Sender):
    channel: str = "email"
    host: str = ""
    port: int = 587
    username: str | None = None
    password: str | None = None
    sender_address: str = "spec-review@localhost"
    use_tls: bool = True
    # Injectable transport for tests: a callable(EmailMessage) -> None.
    transport: Optional[Callable[[EmailMessage], None]] = None

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "SmtpSender":
        return cls(
            host=env["SMTP_HOST"],
            port=int(env.get("SMTP_PORT", "587")),
            username=env.get("SMTP_USERNAME"),
            password=env.get("SMTP_PASSWORD"),
            sender_address=env.get("SMTP_FROM", "spec-review@localhost"),
            use_tls=env.get("SMTP_TLS", "true").lower() != "false",
        )

    def _build_message(self, notification: Notification) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self.sender_address
        msg["To"] = notification.handle
        msg["Subject"] = notification.subject
        msg.set_content(notification.body)
        return msg

    def send(self, notification: Notification) -> None:
        msg = self._build_message(notification)
        if self.transport is not None:
            self.transport(msg)
            return
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(msg)
