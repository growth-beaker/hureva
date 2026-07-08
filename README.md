# hureva

A **spec review & approval workflow** you install into your team's repo: generate
specs with Claude, get structured review from non-technical teammates (PM, UX, QA)
**before code is written**, and record approval in git so it can gate the build.
Based on [`docs/spec-review-workflow-specification.md`](docs/spec-review-workflow-specification.md).

hureva is a **versioned package teams install, not copy**. Your specs live in your
own repo under `specs/`; you add a small workflow that `pip install`s a pinned
version of `hureva` and runs it, plus a bit of config. Nothing is hosted, and none
of hureva's code lives in your repo.

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

## How teams install it

hureva is a **PyPI package** (`hureva`), published on each GitHub Release. The
fastest path is to scaffold the setup, then follow the printed checklist:

```bash
pip install hureva
hureva-init            # writes the workflow + config, prints next steps
```

Under the hood that adds one small, static workflow that installs the versioned
package and runs its two commands — notify, then gate:

```yaml
# team-repo/.github/workflows/spec-review.yml
on:
  push:
    branches: ["spec/**"]     # status changes happen on spec branches (§7.4)
    paths: ["specs/**"]       # (literal — Actions can't use a variable here)
jobs:
  spec-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # both push commits reachable (§7.4)
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install "hureva~=1.0"                 # ← version pin lives here
      - run: hureva-notify --specs-dir specs
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          # SMTP_* too, if using email
      - run: hureva-gate --changed --specs-dir specs   # add --enforced to block
```

Nothing of hureva's code lives in the team repo — the workflow is generic "install
a tool and run it" plumbing, and all behavior is in the versioned package.

### Versioning — pin the package

`pip install "hureva~=1.0"` is the version pin (like `"hureva": "^1.0"` in a
dependency list). It's the alternative to copying hureva's code in (which drifts
and never gets fixes): you install a released version.

- `~=1.0` takes any 1.x release, so compatible fixes flow in automatically.
- Pin exactly with `==1.2.3`; move to the next major (`~=2.0`) when *you* choose,
  after reading its release notes.

## CLIs

Commands (also runnable as `python -m hureva.<module>`). The operational ones take
`--specs-dir` (default `specs`).

```bash
# One-time: scaffold the workflow + config into this repo, print next steps
hureva-init

# Create a spec + its spec/<slug> branch (seeds roles from defaults.yml)
hureva-new-spec <slug> --title "Feature title"

# Route notifications for a push (--dry-run prints without delivering)
hureva-notify --dry-run

# Gate the specs changed in a push
hureva-gate --changed                # advisory (exit 0)
hureva-gate --changed --enforced     # block if not approved
hureva-gate <slug> --require-all-approvers   # gate one spec by slug
```

`hureva-notify` / `hureva-gate --changed` read the GitHub push event
(`$GITHUB_EVENT_PATH`, set by the runner; or `--event-file`) to get the
`before`/`after` commits. Recipients come from the spec's frontmatter roles; each
person's channel is their handle in `roster.yml`. A name missing from the roster
is reported loudly, never dropped silently.

## Channels

Each person is reached on the channel whose handle you give them in `roster.yml`
(list only one; the order below breaks ties):

- **GitHub** — `github: <username>`. **No setup** — the workflow's built-in
  `GITHUB_TOKEN` opens a PR for the spec branch and requests the person as a
  reviewer, so GitHub emails/notifies them. They just need access to the repo.
- **Slack** — `slack: "<U-id>"`; set the `SLACK_BOT_TOKEN` secret. Handles:
  `#channel`, a member ID (`U…`), or an email (DM via `users.lookupByEmail`).
- **SMTP email** — `email: <addr>`; set `SMTP_HOST` (+ `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD`, `SMTP_FROM`).

GitHub works out of the box; Slack/email activate only when their secret is set.
`--dry-run` needs no credentials.

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
