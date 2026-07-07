"""hureva-init — scaffold spec review into the current repo, then guide the rest.

Run once in your repo after `pip install hureva`. It writes the workflow and the
config files (asking only for the specs path), skips anything that already exists,
and prints a checklist for the steps that can't be automated (Slack app, secret,
commit, GitBook). It touches nothing else — no git, no secrets, no network.
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


def _roster() -> str:
    return """\
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
  chris:   { github: chris }
  elena:   { github: elena-pm }
  sam:     { github: sam-ux }
  qa-team: { github: qa-lead }
"""


def _defaults() -> str:
    return """\
# Default review assignment, copied into a NEW spec's frontmatter at creation,
# then freely overridden per spec. A seed, not a runtime fallback.
owner: chris
approvers: [elena]
commenters: [sam]
viewers: [qa-team]
"""


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


def render_files(specs_dir: str = "specs") -> dict[str, str]:
    """The whole scaffold as {relative_path: content}."""
    return {
        ".github/workflows/spec-review.yml": _workflow(specs_dir),
        f"{specs_dir}/roster.yml": _roster(),
        f"{specs_dir}/defaults.yml": _defaults(),
        f"{specs_dir}/spec.template.md": _spec_template(),
        "CLAUDE.md": _claude_md(specs_dir),
        ".claude/commands/new-spec.md": _new_spec_cmd(specs_dir),
    }


def scaffold(target: Path, specs_dir: str, force: bool) -> tuple[list[str], list[str]]:
    """Write the scaffold. Returns (written, skipped) relative paths."""
    written: list[str] = []
    skipped: list[str] = []
    for rel, content in render_files(specs_dir).items():
        dest = target / rel
        if dest.exists() and not force:
            skipped.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(rel)
    return written, skipped


def _prompt_specs_dir(default: str = "specs") -> str:
    if not sys.stdin.isatty():  # non-interactive (CI, pipe) — take the default
        return default
    try:
        answer = input(f"Where should specs live? [{default}]: ").strip()
    except EOFError:
        return default
    return answer or default


_CHECKLIST = """\
Next steps (the parts that can't be scaffolded):

  1. Fill in {specs_dir}/roster.yml and {specs_dir}/defaults.yml with your team.

  2. Create a Slack app + bot token:
       - https://api.slack.com/apps  →  Create New App  →  From scratch
       - Bot Token Scopes: chat:write, users:read.email
       - Install to Workspace, copy the xoxb-… token, invite the bot to channels

  3. Add the token as a repo secret named SLACK_BOT_TOKEN:
       gh secret set SLACK_BOT_TOKEN
     (or Settings → Secrets and variables → Actions)

  4. Commit and push to your default branch, then merge:
       git add .github/workflows/spec-review.yml {specs_dir} CLAUDE.md .claude/
       git commit -m "Add spec review & approval workflow"

  5. Connect your docs tool (GitBook/ReadMe): enable git sync at this repo and map
     roles → permissions (viewers→read, commenters→comment, approvers→edit, owner→admin).

  6. Create your first spec:
       hureva-new-spec <slug> --title "Feature title" --specs-dir {specs_dir}

See SETUP.md for the full walkthrough.\
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hureva-init",
        description="Scaffold spec review into this repo, then print next steps.",
    )
    parser.add_argument(
        "--specs-dir",
        help="where specs live (default: prompt, or 'specs' when non-interactive)",
    )
    parser.add_argument("--into", default=".", help="target repo directory (default: .)")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args(argv)

    specs_dir = args.specs_dir or _prompt_specs_dir()
    written, skipped = scaffold(Path(args.into), specs_dir, args.force)

    for rel in written:
        print(f"  created  {rel}")
    for rel in skipped:
        print(f"  skipped  {rel} (exists — use --force to overwrite)")
    if not written:
        print("\nNothing written; all files already exist.")
    print()
    print(_CHECKLIST.format(specs_dir=specs_dir))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
