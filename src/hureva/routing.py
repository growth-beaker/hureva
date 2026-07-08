"""Routing: event → recipients (by role) → person → channel (§7.1).

Routing is *derived from the frontmatter roles* — there is no separate routing
config (§7). The event fixes which roles are reached; the frontmatter fixes who
is in each role; the roster fixes each person's channel. Channel default: Slack
if present, else email (§4.3). A person missing from the roster fails loudly (the
owner is notified), never silently.
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import Event, EVENT_TITLES, Notification
from .models import Roster, SpecFrontmatter


class RosterResolutionError(LookupError):
    """A recipient name is not present in the roster (§4.3: fail loudly)."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("names missing from roster: " + ", ".join(missing))


@dataclass(frozen=True)
class ResolvedRecipient:
    person: str  # roster key
    channel: str  # "slack" | "email"
    handle: str  # slack handle or email address


def recipients_for_event(spec: SpecFrontmatter, event: Event) -> list[str]:
    """Which role members an event reaches (§7.1). Returns person keys, deduped.

    - ``ready_for_review`` → approvers + commenters + viewers
    - ``commented`` → owner
    - ``approved`` / ``cleared_to_build`` → owner
    """
    if event is Event.ready_for_review:
        return spec.all_reviewers()
    if event in (Event.commented, Event.approved, Event.cleared_to_build):
        return [spec.owner]
    return []


def resolve_channel(roster: Roster, person: str) -> ResolvedRecipient:
    """Resolve one person key to a channel, in preference order: slack, email, github.

    Order only breaks ties: to reach someone on a specific channel, list only that
    handle for them. Raises :class:`RosterResolutionError` if the person is absent
    or has no handle (which the roster model already forbids, but we guard anyway).
    """
    entry = roster.get(person)
    if entry is None:
        raise RosterResolutionError([person])
    if entry.slack:
        return ResolvedRecipient(person=person, channel="slack", handle=entry.slack)
    if entry.email:
        return ResolvedRecipient(person=person, channel="email", handle=entry.email)
    if entry.github:
        return ResolvedRecipient(person=person, channel="github", handle=entry.github)
    raise RosterResolutionError([person])


def resolve_recipients(
    roster: Roster, people: list[str]
) -> tuple[list[ResolvedRecipient], list[str]]:
    """Resolve many person keys. Returns (resolved, missing).

    Missing names are collected rather than raised so the caller can deliver the
    ones that resolved *and* loudly report the ones that didn't (§4.3).
    """
    resolved: list[ResolvedRecipient] = []
    missing: list[str] = []
    for person in people:
        try:
            resolved.append(resolve_channel(roster, person))
        except RosterResolutionError:
            missing.append(person)
    return resolved, missing


def _default_body(event: Event, slug: str, links: dict[str, str]) -> str:
    lines = [EVENT_TITLES[event], "", f"Spec: {slug}"]
    for label, url in links.items():
        lines.append(f"{label}: {url}")
    return "\n".join(lines)


def build_notifications(
    spec: SpecFrontmatter,
    event: Event,
    roster: Roster,
    slug: str,
    links: dict[str, str] | None = None,
) -> tuple[list[Notification], list[str]]:
    """End-to-end for one (spec, event): recipients → resolved → notifications.

    Returns (notifications, missing_names). ``missing_names`` is non-empty when a
    named recipient is absent from the roster; the caller notifies the owner.
    """
    links = links or {}
    people = recipients_for_event(spec, event)
    resolved, missing = resolve_recipients(roster, people)

    subject = f"[{slug}] {EVENT_TITLES[event]}"
    body = _default_body(event, slug, links)

    notifications = [
        Notification(
            event=event,
            slug=slug,
            recipient=r.person,
            channel=r.channel,
            handle=r.handle,
            subject=subject,
            body=body,
            links=dict(links),
        )
        for r in resolved
    ]
    return notifications, missing
