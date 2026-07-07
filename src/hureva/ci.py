"""One-shot CI entrypoint: notify + gate for a push (§6, §7).

This is what the workflow runs in a single step (`hureva ci`). It discovers the
specs changed in the push once, notifies their reviewers, then gates them —
returning the gate's exit code so an enforced gate can fail the job. Keeping the
whole run in the versioned package means the workflow YAML stays trivial and
static; there is nothing workflow-shaped left to version separately.
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import Paths, load_roster
from .discovery import discover_changes, load_event
from .frontmatter import parse_spec
from .gate import evaluate_gate, _report_result
from .gitref import GitReader
from .notify import _report as _notify_report, dispatch, process_push
from .senders import build_sender


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hureva ci",
        description="Notify reviewers and gate the specs changed in a push.",
    )
    parser.add_argument("--specs-dir", default=os.environ.get("SPECS_DIR", "specs"))
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument(
        "--enforced",
        action="store_true",
        help="exit non-zero when a changed spec is not approved",
    )
    parser.add_argument("--require-all-approvers", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="route + print, but don't deliver"
    )
    parser.add_argument(
        "--event-file",
        default=os.environ.get("GITHUB_EVENT_PATH"),
        help="path to the GitHub push event JSON",
    )
    args = parser.parse_args(argv)

    paths = Paths(args.specs_dir)
    roster = load_roster(args.specs_dir)
    git = GitReader(args.repo_dir)

    changes = discover_changes(paths, git, load_event(args.event_file))
    if not changes:
        print("no spec changes in this push; nothing to do")
        return 0

    # Notify first — reviewers hear about the change even if the gate later blocks.
    results = process_push(changes, roster)
    dispatch(results, build_sender(dry_run=args.dry_run))
    _notify_report(results, dry_run=args.dry_run)

    # Then gate each changed spec, using the pushed (after) content.
    print("---")
    exit_code = 0
    for change in changes:
        if change.after_text is None:  # deletion
            continue
        spec = parse_spec(change.after_text)
        result = evaluate_gate(
            spec, slug=change.slug, require_all_approvers=args.require_all_approvers
        )
        exit_code |= _report_result(result, args.enforced)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
