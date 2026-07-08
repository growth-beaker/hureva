"""Delivery behind an interface (§12.4, §7.3).

``Sender.send(notification)`` is the one seam every delivery mechanism implements.
The hosted version (option 3) swaps in per-tenant OAuth connectors without
touching routing. A :class:`DryRunSender` records instead of delivering, giving
the library its ``--dry-run`` mode (handoff §0).

``build_sender`` assembles a :class:`MultiSender` that dispatches each
notification to the sender matching its ``channel``, so routing stays channel-
agnostic and a team simply doesn't wire up channels it lacks (§13.6).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..events import Notification


class Sender(ABC):
    """Delivers a :class:`Notification` over one channel."""

    #: The channel string this sender handles ("slack" | "email").
    channel: str

    @abstractmethod
    def send(self, notification: Notification) -> None:  # pragma: no cover - abstract
        ...


@dataclass
class DryRunSender(Sender):
    """Records notifications instead of delivering them.

    Handles every channel, so a fully offline ``--dry-run`` never needs real
    credentials. The recorded list is the assertion surface for tests and the CLI.
    """

    channel: str = "*"
    sent: list[Notification] = field(default_factory=list)

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)


class MultiSender:
    """Dispatches each notification to the sender registered for its channel."""

    def __init__(self, senders: dict[str, Sender], fallback: Sender | None = None):
        self._senders = senders
        self._fallback = fallback

    def send(self, notification: Notification) -> None:
        sender = self._senders.get(notification.channel, self._fallback)
        if sender is None:
            raise LookupError(
                f"no sender configured for channel {notification.channel!r}"
            )
        sender.send(notification)


def build_sender(dry_run: bool = False, env: dict[str, str] | None = None) -> MultiSender:
    """Build the active sender set from the environment (§13.6).

    ``dry_run`` short-circuits to a single :class:`DryRunSender` for all channels.
    Otherwise each channel is enabled only if its credentials are present, so a
    team with no SMTP simply doesn't enable the SMTP sender.
    """
    env = os.environ if env is None else env

    if dry_run:
        dry = DryRunSender()
        return MultiSender({"slack": dry, "email": dry, "github": dry}, fallback=dry)

    senders: dict[str, Sender] = {}

    slack_token = env.get("SLACK_BOT_TOKEN")
    if slack_token:
        from .slack import SlackSender

        senders["slack"] = SlackSender(token=slack_token)

    if env.get("SMTP_HOST"):
        from .email import SmtpSender

        senders["email"] = SmtpSender.from_env(env)

    # GitHub needs no configured secret — the workflow's built-in GITHUB_TOKEN is
    # enough — so this channel is available by default inside Actions.
    if env.get("GITHUB_TOKEN") and env.get("GITHUB_REPOSITORY"):
        from .github import GitHubSender

        senders["github"] = GitHubSender(
            token=env["GITHUB_TOKEN"],
            repository=env["GITHUB_REPOSITORY"],
            base_branch=env.get("HUREVA_BASE_BRANCH"),  # None => auto-detect default
            api_url=env.get("GITHUB_API_URL", "https://api.github.com"),
        )

    return MultiSender(senders)


__all__ = ["Sender", "DryRunSender", "MultiSender", "build_sender"]
