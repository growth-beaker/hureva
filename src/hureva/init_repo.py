"""hureva-init — friendly, interactive setup for spec review in the current repo.

Run once after `pip install hureva`. It asks where specs live, then walks you
through building the team roster — starting with you and encouraging you to add
teammates — and writes the workflow, config, and Claude aids. It skips files that
already exist, and prints a short checklist for the rest (commit, GitBook, and
Slack/email only if you use them).

Non-interactive (piped, CI, or `--sample`) falls back to writing a sample roster,
so automation still works. It never commits or sets secrets; the only network call
is a best-effort `gh api user` to pre-fill your GitHub username.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _workflow(specs_dir: str) -> str:
    return f"""\
# Spec review & approval. On a push to a spec branch, notify reviewers and gate
# the changed specs. All behavior lives in the versioned `hureva` package; this
# file is just "install the tool and run it" and rarely changes.
name: spec-review

on:
  push:
    branches: ["spec/**"]     # status changes happen on spec branches
    paths: ["{specs_dir}/**"]

# Lets the GitHub notify channel open a PR and request reviewers with the
# built-in GITHUB_TOKEN — no extra secret needed.
permissions:
  contents: read
  pull-requests: write

jobs:
  spec-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0       # both push commits reachable for transition detection
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "hureva~=1.0"     # version pin
      - run: hureva-notify --specs-dir {specs_dir}
        env:
          # GitHub channel: works out of the box, no secret to set.
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
          # Slack / email are used only if their secret is set.
          SLACK_BOT_TOKEN: ${{{{ secrets.SLACK_BOT_TOKEN }}}}
          SMTP_HOST: ${{{{ secrets.SMTP_HOST }}}}
          SMTP_PORT: ${{{{ secrets.SMTP_PORT }}}}
          SMTP_USERNAME: ${{{{ secrets.SMTP_USERNAME }}}}
          SMTP_PASSWORD: ${{{{ secrets.SMTP_PASSWORD }}}}
          SMTP_FROM: ${{{{ secrets.SMTP_FROM }}}}
      # Advisory by default; add --enforced to block un-approved specs and make
      # this a required check with branch protection.
      - run: hureva-gate --changed --specs-dir {specs_dir}
"""


_ROSTER_HEADER = """\
# Central team roster: the only place channels are defined. People are referenced
# everywhere by their key here (name-only); a name missing from this file fails
# loudly rather than silently.
#
# Channel per person (list only the one you want; order breaks ties):
#   github: <username>   — notified via a PR review request. No secrets to set up;
#                          the person just needs access to the repo. Easiest.
#   slack:  "<U-id>"     — needs the SLACK_BOT_TOKEN secret (member ID or #channel).
#   email:  <addr>       — needs the SMTP_* secrets.
people:
"""


def render_roster(people: list[dict]) -> str:
    """Render roster.yml from collected people ({key, github})."""
    lines = [_ROSTER_HEADER.rstrip("\n")]
    for p in people:
        lines.append(f"  {p['key']}: {{ github: {p['github']} }}")
    return "\n".join(lines) + "\n"


def render_defaults(owner: str, roles: dict[str, list[str]]) -> str:
    """Render defaults.yml from an owner and role→keys mapping."""
    fmt = lambda xs: "[" + ", ".join(xs) + "]"  # noqa: E731
    return (
        "# Default review assignment, copied into a NEW spec's frontmatter at\n"
        "# creation, then freely overridden per spec. A seed, not a runtime fallback.\n"
        f"owner: {owner}\n"
        f"approvers: {fmt(roles.get('approvers', []))}\n"
        f"commenters: {fmt(roles.get('commenters', []))}\n"
        f"viewers: {fmt(roles.get('viewers', []))}\n"
    )


def _sample_roster() -> str:
    return render_roster(
        [
            {"key": "chris", "github": "chris"},
            {"key": "elena", "github": "elena-pm"},
            {"key": "sam", "github": "sam-ux"},
            {"key": "qa-team", "github": "qa-lead"},
        ]
    )


def _sample_defaults() -> str:
    return render_defaults(
        "chris", {"approvers": ["elena"], "commenters": ["sam"], "viewers": ["qa-team"]}
    )


def _spec_template() -> str:
    return """\
---
title: <Feature title>
status: draft            # draft | in_review | approved | implemented | archived
owner: chris             # roster key of the driver
approvers: [elena]       # may sign off; recorded in approved_by
commenters: [sam]        # may comment/suggest, not approve
viewers: [qa-team]       # read-only
approved_by: []          # who has actually signed off (subset of approvers)
approved_at: null        # set when status -> approved
version: "1.0"
# prototype: https://...  # optional clickable prototype link
---

# <Feature title>

## Problem

## Proposed solution

## Open questions
"""


def _claude_md(specs_dir: str) -> str:
    return f"""\
# Working with specs in this repo

This repo uses the spec review & approval workflow: specs live here alongside the
code. When you generate a spec, follow these rules so it flows through review and
the gate unchanged.

## Where specs live

- Specs live under `{specs_dir}/<feature-slug>/spec.md`.
- The team roster is `{specs_dir}/roster.yml`; default roles are `{specs_dir}/defaults.yml`.

## How to create a spec

    /new-spec <slug> "Feature title"

or directly:

    hureva-new-spec <slug> --title "Feature title" --specs-dir {specs_dir}

Either seeds roles from `defaults.yml`, writes `{specs_dir}/<slug>/spec.md`, and
creates a `spec/<slug>` branch. Author by hand from `{specs_dir}/spec.template.md`
if you prefer.

## Frontmatter schema (the runtime contract)

    title: string
    status: draft | in_review | approved | implemented | archived
    owner: <roster key>
    approvers: [<roster key>, ...]   # may sign off
    commenters: [<roster key>, ...]  # may comment, not approve
    viewers: [<roster key>, ...]     # read-only
    approved_by: [<roster key>, ...] # subset of approvers
    approved_at: date | null
    version: "semver-ish"

All people are roster keys (names only). Seed unset roles from `defaults.yml`.

## Lifecycle

`draft -> in_review -> approved -> implemented` (plus `archived`). Pushing a spec
with `status: in_review` onto its `spec/<slug>` branch opens it for review and
notifies the reviewers. Move to `approved` only after the team signs off; the
owner records `approved_by`. Do not start the build until `status: approved`.
"""


def _new_spec_cmd(specs_dir: str) -> str:
    return f"""\
---
description: Scaffold a new spec folder, seed roles from defaults.yml, and create its spec/<slug> branch.
argument-hint: <slug> "<Feature title>"
---

Create a new spec for `$ARGUMENTS`.

Run the command below, which reads `{specs_dir}/defaults.yml`, seeds the
frontmatter roles, writes `{specs_dir}/<slug>/spec.md` from the template, and
creates a `spec/<slug>` git branch:

    hureva-new-spec <slug> --title "<Feature title>" --specs-dir {specs_dir}

Then draft the spec body with the user. Leave `status: draft` until they are ready
to open it for review; when they are, set `status: in_review` and push the
`spec/<slug>` branch — that notifies the reviewers.
"""


def _static_files(specs_dir: str) -> dict[str, str]:
    """The scaffold files that aren't roster/defaults."""
    return {
        ".github/workflows/spec-review.yml": _workflow(specs_dir),
        f"{specs_dir}/spec.template.md": _spec_template(),
        "CLAUDE.md": _claude_md(specs_dir),
        ".claude/commands/new-spec.md": _new_spec_cmd(specs_dir),
    }


def render_files(specs_dir: str = "specs") -> dict[str, str]:
    """The whole scaffold as {relative_path: content}, using the sample roster."""
    files = _static_files(specs_dir)
    files[f"{specs_dir}/roster.yml"] = _sample_roster()
    files[f"{specs_dir}/defaults.yml"] = _sample_defaults()
    return files


def _write(target: Path, files: dict[str, str], force: bool) -> tuple[list[str], list[str]]:
    written: list[str] = []
    skipped: list[str] = []
    for rel, content in files.items():
        dest = target / rel
        if dest.exists() and not force:
            skipped.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(rel)
    return written, skipped


def scaffold(target: Path, specs_dir: str, force: bool) -> tuple[list[str], list[str]]:
    """Write the scaffold with the sample roster. Returns (written, skipped)."""
    return _write(target, render_files(specs_dir), force)


# --- interactive prompts --------------------------------------------------------

_ROLE_LABELS = {"approvers": "approver", "commenters": "commenter", "viewers": "viewer"}


def _ask(question: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return answer or (default or "")


def _confirm(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    try:
        answer = input(f"{question} [{hint}]: ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer.startswith("y")


def _detect_github_login() -> str | None:
    """Best-effort current GitHub username via the gh CLI (None if unavailable)."""
    import subprocess

    try:
        result = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _ask_role(key: str) -> str:
    print(f"    What can {key} do?")
    print("      1) approve  — review and sign off")
    print("      2) comment  — suggest, but not approve")
    print("      3) view     — read-only")
    choice = _ask("    Choose 1/2/3", "1")
    return {"1": "approvers", "2": "commenters", "3": "viewers"}.get(choice, "approvers")


def collect_team(default_login: str | None) -> tuple[list[dict], str, dict[str, list[str]]]:
    """Interactively build the roster. Returns (people, owner_key, roles)."""
    print("\nLet's build your team roster — everyone here can be pinged for review.")
    print("We'll start with you.\n")
    you = _ask("Your short name (e.g. 'chris')", default_login or "me")
    you_gh = _ask(f"{you}'s GitHub username", default_login or you)
    people = [{"key": you, "github": you_gh}]
    roles: dict[str, list[str]] = {"approvers": [], "commenters": [], "viewers": []}

    print(f"\n✓ You're the owner, {you} — you'll drive specs and kick off builds.\n")
    print("Now add teammates who should review — PM, UX, QA, other devs.")
    print("The more reviewers you add, the more coverage each spec gets.\n")
    while _confirm("Add a teammate?", default=True):
        key = _ask("  Their short name")
        if not key:
            break
        github = _ask(f"  {key}'s GitHub username", key)
        role = _ask_role(key)
        people.append({"key": key, "github": github})
        roles[role].append(key)
        label = _ROLE_LABELS[role]
        article = "an" if label[0] in "aeiou" else "a"
        print(f"  ✓ Added {key} as {article} {label}.\n")

    if len(people) == 1:
        print("(Flying solo for now — add teammates any time by editing roster.yml.)\n")
    return people, you, roles


_WELCOME = "\n👋  Let's set up spec review in this repo.\n"


def _preflight(target: Path) -> None:
    """Friendly, non-blocking warnings before we invest in setup."""
    import shutil
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True,
        )
        in_repo = result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        in_repo = False
    if not in_repo:
        print("⚠  This doesn't look like a git repo. hureva's workflow runs on push,")
        print("   so run `git init` and add a remote before you finish.\n")

    if not shutil.which("gh"):
        print("ℹ  GitHub CLI (gh) not found — I can't pre-fill your username, and")
        print("   you'll add any repo secrets via the GitHub UI. That's fine.\n")


def _confirm_team(people: list[dict], owner: str, roles: dict[str, list[str]]) -> bool:
    """Show the collected team and confirm before writing anything."""
    role_of = {k: _ROLE_LABELS[role] for role, keys in roles.items() for k in keys}
    print("Here's your team:")
    for p in people:
        role = "owner" if p["key"] == owner else role_of.get(p["key"], "—")
        print(f"  {p['key']:<14}{role}")
    print()
    return _confirm("Write these files?", default=True)


_HOW_IT_WORKS = """\
How it works:
  • hureva-new-spec <slug> --title "…"  creates a spec on a spec/<slug> branch.
  • Set status: in_review and push  →  your reviewers are notified.
  • They approve → set status: approved → you build. (Enforce the gate later.)
"""


def _next_steps(specs_dir: str) -> str:
    return f"""\
Next steps:

  1. Make sure everyone in {specs_dir}/roster.yml can access this repo — they're
     requested as GitHub reviewers, so they need to see it.

  2. Commit and push to your default branch, then merge:
       git add .github/workflows/spec-review.yml {specs_dir} CLAUDE.md .claude/
       git commit -m "Add spec review & approval workflow"

  3. Create your first spec:
       hureva-new-spec <slug> --title "Feature title" --specs-dir {specs_dir}

  Optional:
   • Prefer Slack or email for someone? Edit their entry in {specs_dir}/roster.yml
     (github → slack/email) and add the matching repo secret. See SETUP.md.
   • Connect GitBook/ReadMe git-sync for a non-Git review surface.

See SETUP.md for the full walkthrough."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hureva-init",
        description="Set up spec review in this repo (interactive), then print next steps.",
    )
    parser.add_argument(
        "--specs-dir",
        help="where specs live (default: ask, or 'specs' when non-interactive)",
    )
    parser.add_argument("--into", default=".", help="target repo directory (default: .)")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="skip the interactive team setup; write the sample roster",
    )
    args = parser.parse_args(argv)

    target = Path(args.into)
    interactive = sys.stdin.isatty() and not args.sample

    if interactive:
        print(_WELCOME)
        _preflight(target)
    specs_dir = args.specs_dir or (
        _ask("Where should specs live?", "specs") if interactive else "specs"
    )

    files = _static_files(specs_dir)
    roster_rel = f"{specs_dir}/roster.yml"
    defaults_rel = f"{specs_dir}/defaults.yml"
    roster_exists = (target / roster_rel).exists()

    if interactive and not (roster_exists and not args.force):
        people, owner, roles = collect_team(_detect_github_login())
        if not _confirm_team(people, owner, roles):
            print("\nNo changes made — re-run `hureva-init` when you're ready.")
            return 0
        files[roster_rel] = render_roster(people)
        files[defaults_rel] = render_defaults(owner, roles)
    else:
        files[roster_rel] = _sample_roster()
        files[defaults_rel] = _sample_defaults()

    written, skipped = _write(target, files, args.force)

    print("\n✅  Scaffolded:" if interactive else "")
    for rel in written:
        print(f"     {rel}" if interactive else f"  created  {rel}")
    for rel in skipped:
        print(f"     {rel} (kept — already existed)" if interactive
              else f"  skipped  {rel} (exists — use --force to overwrite)")
    if not written:
        print("\nNothing written; all files already exist.")
    print()
    if interactive:
        print(_HOW_IT_WORKS)
    print(_next_steps(specs_dir))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
