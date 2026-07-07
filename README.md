# hureva

The portable core of the **spec review & approval workflow** described in
[`docs/spec-review-workflow-specification.md`](docs/spec-review-workflow-specification.md).

This is the canonical **approval & gate layer** (spec §3) — the load-bearing spine
that holds the system's semantics. The GitHub Actions (a later build step) wrap
this library; they do **not** reimplement its logic (spec §0, decision 13).

> **Scope:** this repository currently contains only the core library (the first
> step in the spec's build order). The reusable workflows, template repo, and
> scaffolder are future steps — see `plan.md`.

## What it does

| Piece | Module | Spec |
|---|---|---|
| Frontmatter / roster / defaults models | `hureva.models` | §4.2–4.4 |
| Frontmatter parsing (+ lenient `status` reader) | `hureva.frontmatter` | §4.2 |
| `specs_dir`-derived paths, config loading, defaults seeding | `hureva.config` | §4.1, §4.4, §13.5 |
| Two-commit transition detection (pure fn) | `hureva.transitions` | §7.4 |
| Event → role → person → channel routing | `hureva.routing` | §7.1 |
| Sender interface + dry-run + Slack + SMTP | `hureva.senders` | §7.3, §12.4 |
| Notify orchestration + CLI | `hureva.notify` | §7 |
| Status gate + CLI (advisory / enforced) | `hureva.gate` | §6 |

Design seams that keep a future hosted service additive (spec §12.4): the logic is
a pure library (git/env reading is a thin shell), delivery is behind a `Sender`
interface, events are a defined schema, and `specs_dir` is per-tenant data — no
path is ever hard-coded.

## Install & test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## CLIs

Both take `--specs-dir` (default `specs`) so nothing hard-codes the path.

```bash
# Notify: detect the transition in a push and route notifications.
# --dry-run prints who would be notified without delivering.
python -m hureva.notify --specs-dir specs --dry-run

# Gate: read a spec's status and decide whether the build is cleared.
python -m hureva.gate <slug> --specs-dir specs              # advisory (exit 0)
python -m hureva.gate <slug> --specs-dir specs --enforced   # block if not approved
python -m hureva.gate <slug> --specs-dir specs --enforced --require-all-approvers
```

`hureva.notify` reads a GitHub push event (`$GITHUB_EVENT_PATH`, or `--event-file`)
to get the `before`/`after` commits, then compares `status` across them — firing
`ready_for_review` on `→ in_review` and `approved` on `→ approved`, and nothing on
a body-only edit (the dedup). Recipients come from the spec's frontmatter roles;
each channel is resolved from `roster.yml` (Slack if present, else email). A name
missing from the roster is reported loudly, never dropped silently.

## Channels

Delivery is enabled by the environment (spec §13.6):

- **Slack** — set `SLACK_BOT_TOKEN` (DMs resolve via `users.lookupByEmail`).
- **SMTP email** — set `SMTP_HOST` (+ `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
  `SMTP_FROM`, `SMTP_TLS`). Optional; a team without SMTP simply doesn't set it.

`--dry-run` needs no credentials at all.
