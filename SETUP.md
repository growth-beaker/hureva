# Installing hureva in your team's repo

Your specs live in your own repo under `specs/`. You install hureva as a
**versioned package**: add one small workflow that `pip install`s it and runs it,
and a bit of config. With GitHub notifications (the default) there are no secrets
to set up. None of hureva's code lives in your repo.

Reviewers (PM/UX/QA) install **nothing** — they review in GitBook/ReadMe in a
browser.

---

## Quick start

From the root of your repo:

```bash
pip install hureva
hureva-init            # asks where specs live, then scaffolds the files
```

`hureva-init` writes the workflow and config files and prints a checklist for the
parts that can't be scaffolded (fill the roster, commit, GitBook — plus Slack/email
only if you use them). Follow that
checklist and you're done. The rest of this document is the same steps in detail.

---

## How the install works (the 30-second version)

hureva is a **PyPI package** (`hureva`). Your repo gets a small, static workflow
that installs a pinned version and runs its two commands — notify, then gate. The
workflow is generic "install a tool and run it" plumbing; all the behavior — and
all the versioning — lives in the package.

```yaml
# your-repo/.github/workflows/spec-review.yml
on:
  push:
    branches: ["spec/**"]
    paths: ["specs/**"]
jobs:
  spec-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install "hureva~=1.0"
      - run: hureva-notify --specs-dir specs
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
      - run: hureva-gate --changed --specs-dir specs
```

### What does `hureva~=1.0` mean?

`pip install "hureva~=1.0"` is a *version pin*, just like `"hureva": "^1.0"` in a
dependency list. It says "any 1.x release."

- Your setup behaves consistently; compatible fixes (1.x) flow in automatically.
- A new **major** version (`2.0`) does **nothing** to you until you change that one
  line to `~=2.0` — you upgrade on your schedule. Pin exactly with `==1.2.3` if you
  want zero drift.

This is the opposite of copying hureva's code in (which would drift and never get
fixes). You install a released version and opt into upgrades.

---

## Step 1 — Add the workflow

*(`hureva-init` already wrote this — skip to Step 2 if you ran it.)*

Create `.github/workflows/spec-review.yml` in your repo with the YAML above.

- **Specs elsewhere?** If you keep specs under, say, `docs/specs`, set both the
  `paths:` filter and `--specs-dir docs/specs` to match. (The `paths:` value must
  be a literal — GitHub Actions can't use a variable there.)
- **Email too?** Add `SMTP_HOST` (+ `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
  `SMTP_FROM`) to the `env:` block alongside `SLACK_BOT_TOKEN`.
- **Enforce later:** add `--enforced` to the `hureva-gate` line when you want CI to
  block un-approved specs (Step 7). Start without it.

---

## Step 2 — Add your config

*(`hureva-init` wrote starter versions of these — edit them with your real team.)*

Two files under `specs/` (or your chosen path). Everything references people by
**roster key** (short name), never by inline handles.

`specs/roster.yml` — the only place channels are defined. Give each person **one**
handle; that picks how they're reached:

```yaml
people:
  chris:   { github: chris }       # notified via GitHub — no setup (Step 3 is optional)
  elena:   { github: elena-pm }
  sam:     { github: sam-ux }
  qa-team: { github: qa-lead }
```

- **`github: <username>`** — the easiest: the workflow opens a PR and requests them
  as a reviewer using the built-in token, so GitHub emails/notifies them. They just
  need access to the repo. **No secret to configure.**
- **`slack: "<U-id>"`** — needs the `SLACK_BOT_TOKEN` secret (Step 3). Use a member
  ID (`U…`) for DMs or `#channel` for a group.
- **`email: <addr>`** — needs the `SMTP_*` secrets.

`specs/defaults.yml` — copied into each **new** spec at creation, overridable per spec:

```yaml
owner: chris
approvers: [elena]
commenters: [sam]
viewers: [qa-team]
```

*(Optional authoring aids: `CLAUDE.md`, `specs/spec.template.md`, and
`.claude/commands/new-spec.md` — `hureva-init` writes these too.)*

---

## Step 3 — (Optional) Slack or email

**Skip this if you're using GitHub notifications** (the default) — there's nothing
to configure. Set this up only for people you gave a `slack:` or `email:` handle.

**Slack:**
1. <https://api.slack.com/apps> → **Create New App** → *From scratch* → your workspace.
2. **OAuth & Permissions → Bot Token Scopes**: add `chat:write` and `users:read.email`.
3. **Install to Workspace**, copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Invite the bot** to any channel you use as a roster target (`/invite @your-bot`).
5. Repo → **Settings → Secrets and variables → Actions** → add `SLACK_BOT_TOKEN`.

**Email:** add `SMTP_HOST` (+ `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
`SMTP_FROM`) as repo secrets.

The workflow already passes all of these to `hureva-notify`; each channel activates
only when its secret is present.

*Email (optional):* also add `SMTP_HOST` (+ `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_FROM`) to deliver email too.

---

## Step 4 — Commit to your default branch

The caller workflow must exist on `main` so spec branches cut from `main` inherit
it (GitHub runs a push-triggered workflow using the file as it exists on the
pushed branch).

```bash
git checkout -b add-spec-review
git add .github/workflows/spec-review.yml specs/
git commit -m "Add spec review & approval (hureva)"
git push -u origin add-spec-review   # open a PR and merge into main
```

---

## Step 5 — Connect your docs tool (GitBook or ReadMe)

One-time dashboard step, no code:

1. Enable **Git Sync** and point it at your repo (scope it to `specs/` if allowed).
2. Map roles → permission levels once: `viewers → read`, `commenters → comment`,
   `approvers → edit/review`, `owner → admin`.

Reviewers now read and comment in the browser; edits sync back as commits.

---

## Step 6 — Create your first spec

Install the CLI locally (spec authors only):

```bash
pipx install hureva     # or: pip install hureva
```

Then, from `main`:

```bash
git checkout main && git pull
hureva-new-spec checkout-redesign --title "Checkout Redesign"
```

This seeds roles from `defaults.yml`, writes `specs/checkout-redesign/spec.md`, and
creates the `spec/checkout-redesign` branch. Draft the body, then open it for
review by setting the status and pushing:

```yaml
# in specs/checkout-redesign/spec.md frontmatter
status: in_review
```

```bash
git add specs/checkout-redesign/spec.md
git commit -m "Open checkout redesign for review"
git push -u origin spec/checkout-redesign
```

The push triggers your `spec-review.yml`, which runs notify then gate:

- **notify** detects `draft → in_review` and messages approvers + commenters +
  viewers with a link.
- **gate** reports the spec isn't approved yet (advisory — it doesn't block).

When the team signs off, the owner records it and moves to `approved`:

```yaml
status: approved
approved_by: [elena]
```

Push again — notify messages the **owner** "ready to build," the gate reports
`cleared_to_build`, and you start the build yourself (nothing runs automatically).

### Rehearse without sending

After committing a status change on a spec branch, preview routing with no delivery:

```bash
hureva-notify --dry-run \
  --event-file <(printf '{"before":"%s","after":"%s"}' "$(git rev-parse HEAD~1)" "$(git rev-parse HEAD)")
```

---

## Step 7 — (Later) turn on enforcement

Everything above is **advisory**. To make CI block un-approved specs, add
`--enforced` to the `hureva-gate` line in your workflow:

```yaml
      - run: hureva-gate --changed --specs-dir specs --enforced
```

Then add **branch protection** on `main` and mark the spec-review check
**required**, so an un-approved spec can't merge. Same one line of config.

---

## Upgrading hureva

Patch and minor fixes inside the 1.x line flow in automatically because the
workflow installs `hureva~=1.0`. When hureva releases a new **major** version, bump
that pin (`~=1.0` → `~=2.0`) when you're ready, after reading its release notes. To
freeze the library exactly, use `pip install "hureva==1.2.3"`.

---

## Troubleshooting

- **`pip install "hureva~=1.0"` fails in the run** — hureva must be published to
  PyPI. Until the first release, install from git instead:
  `pip install "hureva @ git+https://github.com/growth-beaker/hureva.git@v1"`.
- **No notification fired** — notify only fires on a *status transition* on a
  `spec/**` branch. A body-only edit, or a push to `main`, fires nothing by design.
- **"name missing from roster"** — someone in a spec's roles isn't in `roster.yml`.
  The notifier reports this loudly instead of dropping them; add them.
- **GitHub reviewer not notified** — the `github:` username must have access to the
  repo (be a collaborator) to be requested as a reviewer; if GitHub rejects the
  request, hureva falls back to an @mention comment on the PR. Also confirm the
  workflow has `permissions: pull-requests: write` (it does by default from
  `hureva-init`).
- **Slack message never arrives** — check the scopes (`chat:write`,
  `users:read.email`), that the bot is invited to the target channel, and that the
  `slack:` handle is a member ID (`U…`) or `#channel`, not a bare `@name`.
