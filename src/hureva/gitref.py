"""Thin git shell for reading a file at a specific commit (§7.4).

Transition detection compares the changed spec against its previous version by
reading ``status`` from the push's ``before`` and ``after`` commits — via
``git show <ref>:<path>``, not ``HEAD~1`` (which breaks on multi-commit and merge
commits, §7.4). This is the only place the library shells out; it is injected
into the orchestration so the pure core stays testable without a git repo.
"""

from __future__ import annotations

import subprocess


class GitReader:
    """Reads file contents at a git ref. Returns ``None`` when the path is absent."""

    def __init__(self, repo_dir: str = "."):
        self.repo_dir = repo_dir

    def read_file_at(self, ref: str, path: str) -> str | None:
        if not ref or ref.strip("0") == "":
            # All-zero SHA is git's "no previous commit" sentinel (new branch).
            return None
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{path}"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            # Path did not exist at that ref (e.g. newly added file).
            return None
        return result.stdout

    def changed_files(self, before: str, after: str) -> list[str]:
        """Files changed between two commits (added/modified/renamed)."""
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{before}", f"{after}"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return [line for line in result.stdout.splitlines() if line]
