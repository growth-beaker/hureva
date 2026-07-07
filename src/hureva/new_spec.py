"""Create a new spec folder + branch in one step (spec §13.8, §14.2).

Reads ``defaults.yml``, seeds the frontmatter roles (overrides win, unset roles
inherit — §4.4), writes ``<specs_dir>/<slug>/spec.md``, and creates the
``spec/<slug>`` branch. The ``/new-spec`` Claude command is a thin wrapper around
this CLI, so bare Claude Code and hand authoring reach the same conformant result.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

from .config import Paths, load_defaults, seed_frontmatter
from .models import ROLE_FIELDS

# Frontmatter key order for a freshly written spec (readability; §4.2 order).
_FIELD_ORDER = (
    "title",
    "status",
    "owner",
    "approvers",
    "commenters",
    "viewers",
    "approved_by",
    "approved_at",
    "version",
)


def _split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def render_spec(title: str, seeded: dict, status: str = "draft", version: str = "1.0") -> str:
    """Render a new spec.md string from seeded roles."""
    frontmatter: dict = {
        "title": title,
        "status": status,
        "owner": seeded.get("owner", ""),
        "approvers": seeded.get("approvers", []),
        "commenters": seeded.get("commenters", []),
        "viewers": seeded.get("viewers", []),
        "approved_by": [],
        "approved_at": None,
        "version": version,
    }
    ordered = {k: frontmatter[k] for k in _FIELD_ORDER}
    yaml_block = yaml.safe_dump(ordered, sort_keys=False, default_flow_style=False)
    return f"---\n{yaml_block}---\n\n# {title}\n\n## Problem\n\n## Proposed solution\n\n## Open questions\n"


def create_spec(
    slug: str,
    title: str,
    specs_dir: str,
    overrides: dict | None = None,
    repo_dir: str = ".",
    make_branch: bool = True,
    force: bool = False,
) -> Path:
    """Write the spec file (and optionally create the branch). Returns its path."""
    paths = Paths(Path(repo_dir) / specs_dir)
    spec_path = paths.spec(slug)
    if spec_path.exists() and not force:
        raise FileExistsError(f"{spec_path} already exists (use --force)")

    defaults = load_defaults(Path(repo_dir) / specs_dir)
    seeded = seed_frontmatter(defaults, overrides)

    if make_branch:
        _git(repo_dir, "checkout", "-b", f"spec/{slug}")

    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(render_spec(title, seeded), encoding="utf-8")
    return spec_path


def _git(repo_dir: str, *args: str) -> None:
    subprocess.run(["git", "-C", repo_dir, *args], check=True, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hureva-new-spec", description=__doc__)
    parser.add_argument("slug", help="feature slug (folder name under <specs_dir>/)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--specs-dir", default="specs")
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--owner")
    parser.add_argument("--approvers", help="comma-separated roster keys")
    parser.add_argument("--commenters", help="comma-separated roster keys")
    parser.add_argument("--viewers", help="comma-separated roster keys")
    parser.add_argument(
        "--no-branch", action="store_true", help="do not create the spec/<slug> branch"
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    overrides: dict = {}
    if args.owner:
        overrides["owner"] = args.owner
    for role in ROLE_FIELDS:
        value = _split_csv(getattr(args, role))
        if value is not None:
            overrides[role] = value

    spec_path = create_spec(
        slug=args.slug,
        title=args.title,
        specs_dir=args.specs_dir,
        overrides=overrides,
        repo_dir=args.repo_dir,
        make_branch=not args.no_branch,
        force=args.force,
    )
    branch_note = "" if args.no_branch else f" on branch spec/{args.slug}"
    print(f"created {spec_path}{branch_note}")
    print("Draft the body, set status: in_review, and push the branch to open review.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
