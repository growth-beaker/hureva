# Setting up spec review in an existing repo

This guide walks a team through adding the spec review & approval workflow to a
repo they **already have**. There is no server to run and no app to install in the
Phase 1 (serverless) build — "installing" means putting a few config files and one
caller workflow into your repo, then pointing your Slack/docs tools at it.

Reviewers (PM/UX/QA) install **nothing** — they review in GitBook/ReadMe in a
browser. Only developers who author specs install a small CLI locally.

---

## The mental model — what actually runs where

There is no central service. Three things cooperate:

| Piece | Where it lives | Who sets it up |
|---|---|---|
| **Central product** (`hureva` library + reusable workflows) | The `growth-beaker/hureva` repo, published at tag `@v1` | Already done — you just reference it |
| **Your repo's config** (`specs/`, `roster.yml`, `defaults.yml`, `spec-review.yml` caller) | Your existing repo | You, once (this guide) |
| **External tools** (Slack, GitBook/ReadMe, optional email) | Their own dashboards | You, once (this guide) |

"Installing" therefore happens in **two** senses, and it helps to keep them apart:

1. **Local CLI install** — on the laptop of anyone who *creates* specs. Gives you
   the `hureva-scaffold` and `hureva-new-spec` commands. One-time, per developer.
2. **Repo install** — the config files + caller workflow committed to your repo.
   The caller workflow references the central reusable workflows at `@v1`; when a
   spec is pushed, **GitHub Actions** checks out your repo and `pip install`s
   `hureva` *inside the runner* automatically. Nothing is installed on your
   servers because there are none.

---

## Prerequisites

- An existing **GitHub repo** you have **admin** access to (to add secrets and,
  later, branch protection).
- **Python 3.12+** locally, for whoever will scaffold and author specs.
- The central repo (`growth-beaker/hureva`) must be **readable by your repo's
  Actions**. The simplest arrangement is that it is **public**. If it is private
  and lives in the same org, enable *Org → Settings → Actions → "Allow access to
  workflows in private repositories"*, or the runtime `pip install` and the
  `uses:` reference will fail.
- A **Slack workspace** where you can create an app (for notifications). Email is
  optional.

---

## Step 1 — Install the `hureva` CLI locally (spec authors only)

The package is not on PyPI; install it straight from the central repo at the tag:

```bash
pip install "hureva @ git+https://github.com/growth-beaker/hureva.git@v1"
```

Prefer a virtual environment or `pipx install` to keep it isolated:

```bash
pipx install "hureva @ git+https://github.com/growth-beaker/hureva.git@v1"
```

Verify:

```bash
hureva-scaffold --help
hureva-new-spec --help
```

Reviewers skip this entirely.

---

## Step 2 — Scaffold the config into your repo

From the **root of your existing repo**, decide where specs should live
(`specs`, or e.g. `docs/specs`) and run the scaffolder:

```bash
cd /path/to/your-repo
hureva-scaffold --into . --specs-dir docs/specs
```

That single `--specs-dir` answer is written into every place that needs it
(the caller workflow inputs, the caller's literal path filter, and the
`CLAUDE.md` guidance) so you only choose it once. It writes:

```
docs/specs/
  roster.yml            # people → slack / email  (fill this in)
  defaults.yml          # default reviewer roles   (fill this in)
  spec.template.md      # blank spec for hand authoring
.github/workflows/
  spec-review.yml       # caller → growth-beaker/hureva ... @v1
CLAUDE.md               # tells Claude Code where specs live + the schema
.claude/commands/
  new-spec.md           # the /new-spec slash command
```

The scaffolder **refuses to overwrite** existing files (so it won't clobber an
existing `CLAUDE.md`). If you hit that, either merge by hand or re-run with
`--force` once you've backed up what you need.

> If your repo already has a `CLAUDE.md`, the scaffolder will stop. Run it once
> into an empty temp dir to see the intended `CLAUDE.md` block, then paste the
> relevant guidance into your existing file.

---

## Step 3 — Fill in `roster.yml` and `defaults.yml`

These are your team's real data. Everything else references people by their
**roster key** (the short name), never by inline email/Slack.

`docs/specs/roster.yml` — the only place channels are defined:

```yaml
people:
  chris:   { email: chris@acme.com, slack: "U01ABC123" }   # Slack member ID (see below)
  elena:   { email: elena@acme.com, slack: "U02DEF456" }
  sam:     { email: sam@acme.com }                          # email only is fine
  qa-team: { slack: "#qa" }                                 # a channel is fine
```

**How a channel is chosen:** for each person the notifier uses **Slack if the
`slack:` field is present, otherwise email**. So if you want someone reached by
email, leave `slack:` off for them.

**Slack handle tips (important):** the `slack:` value is used as the message
target directly, except an email is resolved via `users.lookupByEmail`. For
reliable delivery:

- **Individual DMs → use the Slack member ID** (`U…`, found in a person's Slack
  profile → "Copy member ID"). A bare `@username` is often rejected by modern
  Slack and is not reliable.
- **A group → use the channel** (`#qa`). Invite the bot to that channel (Step 4).
- Alternatively, put an **email** in `slack:` and the bot will DM the matching
  Slack user via `users.lookupByEmail` (needs the `users:read.email` scope).

`docs/specs/defaults.yml` — copied into each **new** spec at creation, then
overridable per spec:

```yaml
owner: chris
approvers: [elena]
commenters: [sam]
viewers: [qa-team]
```

---

## Step 4 — Create a Slack app and bot token

1. Go to <https://api.slack.com/apps> → **Create New App** → *From scratch* →
   pick your workspace.
2. **OAuth & Permissions → Bot Token Scopes**, add:
   - `chat:write` — post messages
   - `users:read.email` — resolve a person's email to their Slack user for DMs
3. **Install to Workspace** and copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Invite the bot** to any channel you use as a roster target
   (e.g. in `#qa`, type `/invite @your-bot`).

(Optional — email instead of / in addition to Slack: have SMTP host/user/pass, or
a transactional API. See Step 5 for the secret names. If you have neither Slack
nor SMTP, you can still rely on GitBook/GitHub's own emails, but then skip the
custom notifier.)

---

## Step 5 — Add the secrets to your repo

GitHub → your repo → **Settings → Secrets and variables → Actions → New
repository secret**. Add:

| Secret | Required | Value |
|---|---|---|
| `SLACK_BOT_TOKEN` | for Slack | the `xoxb-…` token from Step 4 |
| `SMTP_HOST` | for email | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | optional | default `587` |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | for email | SMTP creds (or a Google app password) |
| `SMTP_FROM` | optional | the From: address |

The caller workflow forwards these with `secrets: inherit`; a channel is enabled
only if its secret is present, so a Slack-only team just sets `SLACK_BOT_TOKEN`.

> Managing several team repos? Set these as **organization secrets** scoped to the
> relevant repos so you paste them once, not per repo.

---

## Step 6 — Commit the config to your default branch

The caller workflow must exist on your **default branch (`main`)** so that spec
branches created off `main` inherit it. (GitHub runs a push-triggered workflow
using the workflow file *as it exists on the pushed branch* — branches cut from
`main` will carry `spec-review.yml` with them.)

```bash
git checkout -b add-spec-review
git add docs/specs .github/workflows/spec-review.yml CLAUDE.md .claude/
git commit -m "Add spec review & approval workflow"
git push -u origin add-spec-review
# open a PR and merge it into main
```

After this merges, your repo is "installed."

---

## Step 7 — Connect your docs tool (GitBook or ReadMe)

This is a one-time dashboard step; no code.

1. In GitBook/ReadMe, enable **Git Sync** and point it at your repo (and the
   `docs/specs` path if the tool lets you scope it).
2. Map roles → the tool's permission levels once:
   `viewers → read`, `commenters → comment`, `approvers → edit/review`,
   `owner → admin`.

Reviewers now read and comment on specs in the tool's browser UI; their edits
sync back to the repo as commits.

*(Optional — deploy previews: link the repo in Vercel/Netlify/CF Pages if you want
auto-hosted prototypes per branch. Otherwise a spec just carries a `prototype:`
link in its frontmatter.)*

---

## Step 8 — Create your first spec and watch it flow

From `main`, create a spec (this is what the `/new-spec` command runs under the
hood):

```bash
git checkout main && git pull
hureva-new-spec checkout-redesign --title "Checkout Redesign" --specs-dir docs/specs
```

This seeds roles from `defaults.yml`, writes
`docs/specs/checkout-redesign/spec.md`, and creates the branch
`spec/checkout-redesign`. Draft the body (with Claude Code, or by hand), then open
it for review by setting the status and pushing:

```yaml
# in docs/specs/checkout-redesign/spec.md frontmatter
status: in_review
```

```bash
git add docs/specs/checkout-redesign/spec.md
git commit -m "Open checkout redesign for review"
git push -u origin spec/checkout-redesign
```

The push to `spec/**` triggers `spec-review.yml`:

- **notify** detects `draft → in_review` and messages approvers + commenters +
  viewers with a link.
- **status-gate** reports the spec is not yet approved (advisory — it doesn't
  block anything yet).

When the team signs off in the docs tool, the owner records it and moves the spec
to `approved`:

```yaml
status: approved
approved_by: [elena]
```

Push again — notify messages the **owner** "ready to build," and the gate reports
`cleared_to_build`. You then start the build yourself (nothing runs automatically).

### Try it without sending anything first

To rehearse routing without delivering real messages, run the notifier in
`--dry-run` locally against a push you've already made:

```bash
# after committing a status change on a spec branch
python -m hureva.notify --specs-dir docs/specs --dry-run \
  --event-file <(printf '{"before":"%s","after":"%s"}' "$(git rev-parse HEAD~1)" "$(git rev-parse HEAD)")
```

It prints exactly who *would* be notified, on which channel, and needs no
credentials.

---

## Step 9 — (Later) turn on enforcement

Everything above is **advisory** — the team honors the status socially and the
record lives in git. When you want CI to actually block un-approved specs:

1. In `.github/workflows/spec-review.yml`, set the gate to enforced:
   ```yaml
   gate:
     uses: growth-beaker/hureva/.github/workflows/status-gate.yml@v1
     with:
       specs_dir: docs/specs
       enforced: true                 # exit non-zero unless approved
       # require_all_approvers: true  # optional: every named approver must sign off
     secrets: inherit
   ```
2. Add **branch protection** on `main` and make the `status-gate` check
   **required**, so an un-approved spec can't merge.

Same files, one flag — no redesign.

---

## Troubleshooting

- **`uses:` reference fails / `pip install` fails in the Action** — the central
  `growth-beaker/hureva` repo isn't accessible to your Actions. Make it public or
  allow private-repo workflow access (Prerequisites).
- **No notification fired** — notify only fires on a *status transition* on a
  `spec/**` branch. A body-only edit, or a push to `main`, fires nothing by
  design. Confirm the status actually changed between the two commits.
- **"name missing from roster"** — a person listed in a spec's roles isn't in
  `roster.yml`. The notifier reports this loudly instead of dropping them; add
  them to the roster.
- **Slack message never arrives** — check the bot token scopes (`chat:write`,
  `users:read.email`), that the bot is invited to the target channel, and that
  the `slack:` handle is a member ID (`U…`) or `#channel`, not a bare `@name`.
- **Multi-commit / merge push behaves oddly** — the gate/notify compare the
  push's `before` and `after` commits, so ensure the Action checks out with
  `fetch-depth: 0` (the reusable workflows already set this).
