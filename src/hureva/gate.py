"""Status gate + CLI (§6.2).

Reads ``status`` from a spec's frontmatter. On ``approved`` it clears the build
and emits the ``cleared_to_build`` event (a notification to the owner, "ready to
build" — no automated build runs, §11 decision 21). Two modes (§6.3):

- **advisory** (default): report and exit 0 even when not approved — the build
  warns but proceeds; the record still exists in git.
- **enforced**: exit non-zero when ``status != approved`` so CI blocks the build.

Optional hardening (§6.2): ``--require-all-approvers`` additionally requires that
every named approver has signed off (``approved_by ⊇ approvers``).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from .config import Paths
from .events import Event
from .frontmatter import parse_spec
from .models import SpecFrontmatter, Status


@dataclass(frozen=True)
class GateResult:
    slug: str
    status: Status
    cleared: bool
    event: Event | None
    reason: str


def evaluate_gate(
    spec: SpecFrontmatter, slug: str, require_all_approvers: bool = False
) -> GateResult:
    """Pure gate decision for one spec.

    ``cleared`` is True only when the spec is approved (and, if
    ``require_all_approvers``, every approver has signed off). Emits
    ``cleared_to_build`` exactly when cleared.
    """
    if spec.status != Status.approved:
        return GateResult(
            slug=slug,
            status=spec.status,
            cleared=False,
            event=None,
            reason=f"status is {spec.status.value}, not approved",
        )

    if require_all_approvers:
        outstanding = set(spec.approvers) - set(spec.approved_by)
        if outstanding:
            return GateResult(
                slug=slug,
                status=spec.status,
                cleared=False,
                event=None,
                reason="approved, but awaiting sign-off from: "
                + ", ".join(sorted(outstanding)),
            )

    return GateResult(
        slug=slug,
        status=spec.status,
        cleared=True,
        event=Event.cleared_to_build,
        reason="approved — cleared to build",
    )


def _report_result(result: GateResult, enforced: bool) -> int:
    """Print one gate result and return its contribution to the exit code."""
    if result.cleared:
        print(f"{result.slug}: {result.reason} ({result.event.value})")
        return 0
    if enforced:
        print(f"{result.slug}: BLOCKED — {result.reason}", file=sys.stderr)
        return 1
    print(f"{result.slug}: advisory — {result.reason}; build may proceed")
    return 0


def _slugs_from_push(specs_dir: str, repo_dir: str, event_file: str | None) -> list[str]:
    """Discover the slugs of specs changed in a push (for ``--changed`` mode)."""
    from .discovery import discover_changes, load_event
    from .gitref import GitReader

    changes = discover_changes(
        Paths(specs_dir), GitReader(repo_dir), load_event(event_file)
    )
    # Preserve order, dedupe (a slug appears once even if listed twice).
    return list(dict.fromkeys(c.slug for c in changes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hureva gate", description=__doc__)
    parser.add_argument(
        "slug", nargs="?", help="feature slug under <specs_dir>/ (omit with --changed)"
    )
    parser.add_argument("--specs-dir", default=os.environ.get("SPECS_DIR", "specs"))
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument(
        "--changed",
        action="store_true",
        help="gate every spec changed in the push (from $GITHUB_EVENT_PATH)",
    )
    parser.add_argument(
        "--event-file",
        default=os.environ.get("GITHUB_EVENT_PATH"),
        help="path to the GitHub push event JSON",
    )
    parser.add_argument(
        "--enforced",
        action="store_true",
        help="exit non-zero when status != approved (block the build)",
    )
    parser.add_argument(
        "--require-all-approvers",
        action="store_true",
        help="require approved_by ⊇ approvers before honoring 'approved'",
    )
    args = parser.parse_args(argv)

    paths = Paths(args.specs_dir)

    if args.changed:
        slugs = _slugs_from_push(args.specs_dir, args.repo_dir, args.event_file)
        if not slugs:
            print("no changed specs in this push; nothing to gate")
            return 0
    elif args.slug:
        slugs = [args.slug]
    else:
        parser.error("provide a slug or use --changed")

    exit_code = 0
    for slug in slugs:
        spec = parse_spec(paths.spec(slug).read_text(encoding="utf-8"))
        result = evaluate_gate(
            spec, slug=slug, require_all_approvers=args.require_all_approvers
        )
        exit_code |= _report_result(result, args.enforced)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
