"""Lifecycle events and the notification payload (§7.1).

Events are a **defined contract** (§12.4, "events as a contract"): option 2 emits
them from a git push, a future option-3 service can emit them from a webhook, and
consumers don't care about the source. Keep this module free of git/IO so it
stays a pure schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Event(str, Enum):
    """Notification events (§7.1) plus the gate's ``cleared_to_build`` (§6.2)."""

    ready_for_review = "ready_for_review"
    commented = "commented"
    approved = "approved"
    cleared_to_build = "cleared_to_build"


# Human-facing default titles per event. The routing layer fills in the body.
EVENT_TITLES: dict[Event, str] = {
    Event.ready_for_review: "Spec ready for review",
    Event.commented: "New comment on a spec",
    Event.approved: "Spec approved — ready to build",
    Event.cleared_to_build: "Cleared to build",
}


@dataclass(frozen=True)
class Notification:
    """A message to deliver to one recipient (§7.1 payload).

    ``channel`` and ``handle`` are resolved by routing; ``sender`` picks the
    delivery mechanism off ``channel``. ``links`` carries the review/prototype
    URLs the payload column calls for.
    """

    event: Event
    slug: str
    recipient: str  # roster key
    channel: str  # "slack" | "email"
    handle: str  # slack handle or email address
    subject: str
    body: str
    links: dict[str, str] = field(default_factory=dict)
