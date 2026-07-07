"""Discover changed specs in a push (shared by notify and gate).

Both the notifier and the gate operate on "the ``spec.md`` files that changed in
this push". That discovery — which paths under ``specs_dir`` changed, and their
``before``/``after`` text at the push's two commits (§7.4) — lives here once so
the two CLIs stay in lockstep and the git shell is injected (testable).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import Paths


@dataclass(frozen=True)
class SpecChange:
    """One changed ``spec.md`` with its before/after text (§7.4)."""

    slug: str
    path: str
    before_text: str | None
    after_text: str | None


def _is_spec_under(path: str, specs_dir: str) -> bool:
    under = path.startswith(specs_dir + "/") or path.startswith(specs_dir + os.sep)
    return under and path.endswith("spec.md")


def discover_changes(paths: Paths, git, event: dict) -> list[SpecChange]:
    """Build :class:`SpecChange` objects from a GitHub push event + a GitReader.

    ``event`` is the push payload (``before``/``after`` SHAs). When ``before`` is
    absent (e.g. a manual run), we fall back to ``<after>~1`` so a single-commit
    push still resolves — but the workflow should pass the real event, since
    ``~1`` breaks on merges (§7.4).
    """
    before = event.get("before", "")
    after = event.get("after") or "HEAD"

    if before:
        changed = git.changed_files(before, after)
    else:
        changed = git.changed_files(f"{after}~1", after)

    specs_dir = str(paths.specs_dir)
    changes: list[SpecChange] = []
    for path in changed:
        if not _is_spec_under(path, specs_dir):
            continue
        changes.append(
            SpecChange(
                slug=paths.slug_for(path),
                path=path,
                before_text=git.read_file_at(before, path) if before else None,
                after_text=git.read_file_at(after, path),
            )
        )
    return changes
