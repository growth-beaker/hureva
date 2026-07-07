# Implementation Plan — Spec Review & Approval Workflow (Phase 1 core library)

Derived from `docs/spec-review-workflow-specification.md`. This plan covers **only
the core library** (§13.7 decision 13) — the first build step the handoff notes
(§0) prescribe. The reusable workflows, template repo, and scaffolder are later
steps and are **out of scope for this session**.

## Session decisions

- Package name: `hureva` (the product name for now).
- Central repo: `growth-beaker/hureva` (for future `uses:` references).
- Channels: **Slack + SMTP email**, both implemented behind a sender interface.
- Language: Python 3.12+ (dev on 3.14), Pydantic v2, PyYAML.

## What the core library must do (from the spec)

The Actions wrap this library; they must not reimplement its logic. So the library
owns the entire semantic core:

1. **Models** (§4.2–4.4) — Pydantic models for spec frontmatter, `roster.yml`,
   and `defaults.yml`, with validation (roles are name-only roster keys;
   `approved_by ⊆ approvers`; a person needs at least one channel).
2. **Frontmatter parsing** (§4.2) — split `---` YAML frontmatter from the body;
   a lenient `status`-only reader for the *before* commit, which may predate the
   current schema.
3. **Transition detection** (§7.4) — the one place the "compare two versions"
   rule lives: a pure function `(before_status, after_status) → event | None`.
   Fires only on change; new file → transition into its initial status; a
   multi-state jump fires for the state it landed in.
4. **Routing** (§7.1) — event → recipients (by role) → person → channel. Channel
   default: Slack if present, else email. A person missing from the roster fails
   loudly (owner is notified), never silently.
5. **Senders** (§12.4) — a `notify(recipient, message)` interface with a Slack
   sender (`users.lookupByEmail` + `chat.postMessage`), an SMTP sender, and a
   **dry-run** sender that records instead of delivering.
6. **Gate** (§6.2) — read `status`; on `approved` emit `cleared_to_build`
   (notify the owner "ready to build"); advisory vs enforced mode.
7. **CLIs** — `python -m hureva.notify` and `python -m hureva.gate`, both taking
   `--specs-dir` and `--dry-run`, so the workflows are thin wrappers.

## Module layout

```
src/hureva/
  __init__.py
  models.py         # SpecFrontmatter, Person, Roster, Defaults, Status enum
  frontmatter.py    # split/parse frontmatter; lenient parse_status
  config.py         # load roster.yml / defaults.yml under specs_dir; seed defaults
  events.py         # Event enum + Notification payload
  transitions.py    # detect_event(before_status, after_status) -> Event | None
  routing.py        # event -> recipient person keys -> resolved channels
  gitref.py         # read_file_at(ref, path) via `git show` (injectable, mockable)
  senders/
    __init__.py     # Sender ABC, DryRunSender, build_sender()
    slack.py        # SlackSender
    email.py        # SmtpSender
  notify.py         # orchestration (pure core) + CLI entrypoint
  gate.py           # gate logic + CLI entrypoint
tests/              # pytest unit tests for every pure function
```

## Design seams (kept for Phase 3/4, per §12.4)

- **Logic as a library** — orchestration works on in-memory `SpecChange`
  (before_text/after_text) objects; git/env reading is a thin outer shell, so the
  pure core is unit-testable and reusable by a future hosted service.
- **Delivery behind an interface** — `Sender.send(recipient, notification)`;
  hosted version swaps senders without touching routing.
- **Events as a contract** — `Event` enum + `Notification` dataclass are the
  defined schema emitted by push now, by a webhook later.
- **specs_dir is data** — every path derives from a `specs_dir` argument; nothing
  hard-codes `specs`.

## Build order

1. Models + frontmatter (+ tests)
2. Transitions (pure fn) (+ tests)
3. Config loading + defaults seeding (+ tests)
4. Routing (+ tests)
5. Senders (interface + dry-run + Slack + SMTP) (+ tests for dry-run/interface)
6. notify orchestration + CLI, gate + CLI (+ tests)
7. `pyproject.toml`, `README.md`, run full test suite

## Acceptance for this session

- `pytest` green.
- `python -m hureva.notify --specs-dir specs --dry-run` against a sample spec
  prints the routed recipients + messages without sending.
- `python -m hureva.gate --specs-dir specs <slug>` reports gate status.
- No hard-coded `specs` path; no Action logic reimplemented outside the library.
