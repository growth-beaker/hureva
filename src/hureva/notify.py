"""Notify orchestration + CLI (§7).

The pure core is :func:`process_change` / :func:`process_push`, which work on
in-memory ``SpecChange`` objects (before_text / after_text) — no git, no network.
The CLI shell gathers those from a GitHub push event and dispatches through a
:class:`Sender`. Keeping the core pure is the "logic as a library" seam (§12.4):
a future hosted service reuses it unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

from .config import Paths, load_roster
from .discovery import SpecChange, discover_changes
from .events import Event, Notification
from .frontmatter import parse_spec, parse_status
from .models import Roster
from .routing import build_notifications
from .senders import Sender, build_sender


@dataclass
class ChangeResult:
    slug: str
    event: Event | None
    notifications: list[Notification] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def process_change(change: SpecChange, roster: Roster) -> ChangeResult:
    """Detect the transition for one spec and build its notifications.

    Returns a :class:`ChangeResult`; ``event is None`` means no transition fired
    (the dedup case). ``missing`` lists recipients absent from the roster.
    """
    from .transitions import detect_event

    before_status = parse_status(change.before_text)
    after_status = parse_status(change.after_text)
    event = detect_event(before_status, after_status)
    if event is None or change.after_text is None:
        return ChangeResult(slug=change.slug, event=None)

    spec = parse_spec(change.after_text)
    links = _links_from_spec(change.after_text)
    notifications, missing = build_notifications(
        spec=spec, event=event, roster=roster, slug=change.slug, links=links
    )
    return ChangeResult(
        slug=change.slug, event=event, notifications=notifications, missing=missing
    )


def process_push(changes: list[SpecChange], roster: Roster) -> list[ChangeResult]:
    """Process every changed spec in a push."""
    return [process_change(c, roster) for c in changes]


def dispatch(results: list[ChangeResult], sender: Sender) -> None:
    """Deliver all notifications, and alert the owner about any missing names."""
    for result in results:
        for notification in result.notifications:
            sender.send(notification)


def _links_from_spec(text: str) -> dict[str, str]:
    """Pull a prototype link out of the frontmatter if present (§11 decision 22)."""
    from .frontmatter import load_frontmatter_dict

    try:
        data = load_frontmatter_dict(text)
    except Exception:
        return {}
    links: dict[str, str] = {}
    for key in ("prototype", "prototype_link", "review_link"):
        if data.get(key):
            links[key.replace("_", " ")] = str(data[key])
    return links


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hureva-notify", description=__doc__)
    parser.add_argument("--specs-dir", default=os.environ.get("SPECS_DIR", "specs"))
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="detect + route + print, but never deliver",
    )
    parser.add_argument(
        "--event-file",
        default=os.environ.get("GITHUB_EVENT_PATH"),
        help="path to the GitHub push event JSON (defaults to $GITHUB_EVENT_PATH)",
    )
    args = parser.parse_args(argv)

    paths = Paths(args.specs_dir)
    roster = load_roster(args.specs_dir)

    from .gitref import GitReader

    git = GitReader(args.repo_dir)

    event: dict = {}
    if args.event_file and os.path.exists(args.event_file):
        with open(args.event_file, encoding="utf-8") as fh:
            event = json.load(fh)

    changes = discover_changes(paths, git, event)
    results = process_push(changes, roster)

    sender = build_sender(dry_run=args.dry_run)
    dispatch(results, sender)

    _report(results, dry_run=args.dry_run)
    return 0


def _report(results: list[ChangeResult], dry_run: bool) -> None:
    fired = [r for r in results if r.event is not None]
    if not fired:
        print("no status transitions detected; nothing to notify")
        return
    prefix = "[dry-run] would notify" if dry_run else "notified"
    for r in fired:
        print(f"{r.slug}: {r.event.value}")
        for n in r.notifications:
            print(f"  {prefix} {n.recipient} via {n.channel} ({n.handle})")
        for m in r.missing:
            print(f"  !! {m} is not in the roster — owner should be alerted")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
