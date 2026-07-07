# hureva

A **spec review & approval workflow** you install into your team's repo: generate
specs with Claude, get structured review from non-technical teammates (PM, UX, QA)
**before code is written**, and record approval in git so it can gate the build.
Based on [`docs/spec-review-workflow-specification.md`](docs/spec-review-workflow-specification.md).

hureva is a **product teams reference, not copy**. Your specs live in your own
repo under `specs/`; you add an ~8-line workflow that references hureva's reusable
workflow at a pinned version, plus a bit of config. Nothing is hosted, and none of
hureva's code lives in your repo.

> **Installing it? See [`SETUP.md`](SETUP.md)** for the step-by-step guide.

## How it works

- The spec is a `spec.md` whose **frontmatter is the contract** (§4.2): `status`,
  role-based access (`owner`/`approvers`/`commenters`/`viewers`), and the sign-off
  trail. People are named by **roster key**; channels resolve from `specs/roster.yml`.
- Work happens on a `spec/<slug>` branch. Pushing a status change fires the
  workflow, which compares the spec's `status` across the push's two commits and
  acts only on a transition (§7.4).
- `draft → in_review` notifies reviewers; `→ approved` tells the owner "ready to
  build." The gate is advisory by default and can be hardened to block
  un-approved specs (§6.3).

## Library

| Piece | Module | Spec |
|---|---|---|
| Frontmatter / roster / defaults models | `hureva.models` | §4.2–4.4 |
| Frontmatter parsing (+ lenient `status` reader) | `hureva.frontmatter` | §4.2 |
| `specs_dir`-derived paths, config, defaults seeding | `hureva.config` | §4.1, §4.4 |
| Two-commit transition detection (pure fn) | `hureva.transitions` | §7.4 |
| Changed-spec discovery from a push | `hureva.discovery` | §7.4 |
| Event → role → person → channel routing | `hureva.routing` | §7.1 |
| Sender interface + dry-run + Slack + SMTP | `hureva.senders` | §7.3 |
| Notify orchestration + CLI | `hureva.notify` | §7 |
| Status gate + CLI (advisory / enforced) | `hureva.gate` | §6 |
| Create a spec + branch (`/new-spec`) | `hureva.new_spec` | §14.2 |

The logic is a pure library (git/env reading is a thin shell), delivery is behind
a `Sender` interface, and the specs path is configurable — nothing hard-codes
`specs`.

## How teams install it (reference, don't copy)

hureva ships two ways, and teams use both together:

1. A **PyPI package** (`hureva`) — the logic. Published on each GitHub Release.
2. A **reusable workflow** (`.github/workflows/spec-review.yml`, `on: workflow_call`)
   — the ready-made GitHub Actions job. Teams reference it by tag; they never copy
   its contents.

A team adds one small caller workflow to their repo:

```yaml
# team-repo/.github/workflows/spec-review.yml
on:
  push:
    branches: ["spec/**"]     # status changes happen on spec branches (§7.4)
    paths: ["specs/**"]       # (literal — Actions can't use a variable here)
jobs:
  spec-review:
    uses: growth-beaker/hureva/.github/workflows/spec-review.yml@v1
    with: { specs_dir: specs }        # add `enforced: true` to block un-approved specs
    secrets: inherit                  # forwards SLACK_BOT_TOKEN etc.
```

`uses: growth-beaker/hureva/.github/workflows/spec-review.yml@v1` means "run
hureva's `spec-review.yml`, at the version tagged `v1`." At push time GitHub
fetches that workflow at `v1` and runs it against *this* repo — its specs, its
secrets — installing the `hureva` package from PyPI and running the gate + notifier.

### Versioning — what `@v1` does

`@v1` is a **version pin**, exactly like `"hureva": "^1.0"` in a dependency list.
It's the alternative to copying: instead of pasting hureva's code into your repo
(which drifts and never gets fixes), you point at a released version.

- Pin `@v1` and behavior stays stable; hureva shipping `v2` does nothing to you.
- Upgrade when *you* choose, by editing that one line to `@v2`.

The reusable workflow installs the library as `hureva~=1.0` by default (any 1.x
release), so `@v1` picks up compatible fixes automatically; override with
`with: { hureva_version: "==1.2.3" }` to pin exactly.

## CLIs

Every command takes `--specs-dir` (default `specs`).

```bash
# Create a spec + its spec/<slug> branch (seeds roles from defaults.yml)
python -m hureva.new_spec <slug> --title "Feature title"

# Detect the transition in a push and route notifications
# (--dry-run prints who would be notified without delivering)
python -m hureva.notify --dry-run

# Gate the specs changed in a push
python -m hureva.gate --changed              # advisory (exit 0)
python -m hureva.gate --changed --enforced   # block if not approved
# or gate one spec by slug:
python -m hureva.gate <slug> --enforced --require-all-approvers
```

`hureva.notify` / `hureva.gate --changed` read the GitHub push event
(`$GITHUB_EVENT_PATH`, set by the runner; or `--event-file`) to get the
`before`/`after` commits. Recipients come from the spec's frontmatter roles; each
channel resolves from `roster.yml` (Slack if present, else email). A name missing
from the roster is reported loudly, never dropped silently.

## Channels

Delivery is enabled by the environment (§13.6):

- **Slack** — set `SLACK_BOT_TOKEN`. Handles: `#channel`, a member ID (`U…`), or an
  email (DM resolved via `users.lookupByEmail`).
- **SMTP email** — set `SMTP_HOST` (+ `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
  `SMTP_FROM`). Optional; a Slack-only team just doesn't set it.

A channel is used only if its secret is present. `--dry-run` needs no credentials.

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
