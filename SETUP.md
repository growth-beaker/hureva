# Setting up spec review in your repo

Specs live in the **same repo as your code**, under `specs/`. Setup is: add one
workflow file and a little config, wire up Slack, and connect your docs tool.
There is no server and no separate app — the workflow runs on GitHub Actions and
installs the `hureva` tool at runtime.

Reviewers (PM/UX/QA) install **nothing** — they review in GitBook/ReadMe in a
browser. Only developers who author specs install the small CLI locally.

---

## What you're adding

Four files/folders go into your repo:

```
specs/
  roster.yml            # people → slack / email   (edit)
  defaults.yml          # default reviewer roles    (edit)
  spec.template.md      # blank spec for hand authoring
  <feature>/spec.md     # the specs themselves (created later)
.github/workflows/
  spec-review.yml       # gates + notifies on push to spec branches
CLAUDE.md               # tells Claude Code where specs live + the schema
.claude/commands/
  new-spec.md           # the /new-spec slash command
```

The `spec-review.yml` workflow installs `hureva` inside the Actions runner
(`pip install "hureva @ git+https://github.com/growth-beaker/hureva.git@v1"`), so
nothing runs on your infrastructure.

---

## Step 1 — Copy the files in

Grab the four items above from this repo (the `specs/`, `.github/workflows/spec-review.yml`,
`CLAUDE.md`, and `.claude/commands/new-spec.md` here are ready to use) and drop
them into your repo. If your repo already has a `CLAUDE.md`, paste the spec
guidance into it rather than overwriting.

> **Different specs path?** If you'd rather keep specs somewhere other than
> `specs/` (e.g. `docs/specs`), move the folder and update the two `--specs-dir`
> values and the `paths:` filter in `spec-review.yml` to match. That's the only
> place the path is named.

---

## Step 2 — Fill in `roster.yml` and `defaults.yml`

Everything references people by their **roster key** (short name), never by inline
email/Slack.

`specs/roster.yml` — the only place channels are defined:

```yaml
people:
  chris:   { email: chris@acme.com, slack: "U01ABC123" }  # Slack member ID
  elena:   { email: elena@acme.com, slack: "U02DEF456" }
  sam:     { email: sam@acme.com }                         # email only is fine
  qa-team: { slack: "#qa" }                                # a channel is fine
```

- **Channel choice:** Slack is used if `slack:` is present, otherwise email. Leave
  `slack:` off for anyone you want reached by email.
- **Reliable Slack delivery:** use a **member ID** (`U…`, from a person's Slack
  profile → "Copy member ID") for DMs, or a `#channel` for groups. A bare
  `@username` is not reliable. (You can also put an **email** in `slack:` and the
  bot will DM the matching user via `users.lookupByEmail`.)

`specs/defaults.yml` — copied into each **new** spec at creation, overridable per
spec:

```yaml
owner: chris
approvers: [elena]
commenters: [sam]
viewers: [qa-team]
```

---

## Step 3 — Create a Slack app and add the token as a secret

1. <https://api.slack.com/apps> → **Create New App** → *From scratch* → your workspace.
2. **OAuth & Permissions → Bot Token Scopes**: add `chat:write` and
   `users:read.email`.
3. **Install to Workspace**, copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Invite the bot** to any channel you use as a roster target (`/invite @your-bot`
   in `#qa`).
5. In your repo: **Settings → Secrets and variables → Actions → New repository
   secret** → name `SLACK_BOT_TOKEN`, paste the token.

*Email (optional):* if you want email delivery too, also add `SMTP_HOST` (and
`SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`). A channel is used only
if its secret is set, so a Slack-only team sets just `SLACK_BOT_TOKEN`.

---

## Step 4 — Commit to your default branch

The workflow must exist on `main` so that spec branches cut from `main` inherit
it (GitHub runs a push-triggered workflow using the file as it exists on the
pushed branch).

```bash
git checkout -b add-spec-review
git add specs .github/workflows/spec-review.yml CLAUDE.md .claude/
git commit -m "Add spec review & approval workflow"
git push -u origin add-spec-review   # open a PR and merge into main
```

After this merges, your repo is set up.

---

## Step 5 — Connect your docs tool (GitBook or ReadMe)

One-time dashboard step, no code:

1. Enable **Git Sync** and point it at your repo (scope it to `specs/` if the tool
   allows).
2. Map roles → permission levels once: `viewers → read`, `commenters → comment`,
   `approvers → edit/review`, `owner → admin`.

Reviewers now read and comment in the tool's browser UI; their edits sync back to
the repo as commits.

*(Optional — deploy previews: link the repo in Vercel/Netlify/CF Pages for
auto-hosted prototypes per branch. Otherwise a spec carries a `prototype:` link in
its frontmatter.)*

---

## Step 6 — Create your first spec

Install the CLI locally (spec authors only):

```bash
pipx install "hureva @ git+https://github.com/growth-beaker/hureva.git@v1"
```

Then, from `main`:

```bash
git checkout main && git pull
hureva-new-spec checkout-redesign --title "Checkout Redesign"
```

This seeds roles from `defaults.yml`, writes `specs/checkout-redesign/spec.md`, and
creates the `spec/checkout-redesign` branch. Draft the body (with Claude Code or by
hand), then open it for review:

```yaml
# in specs/checkout-redesign/spec.md frontmatter
status: in_review
```

```bash
git add specs/checkout-redesign/spec.md
git commit -m "Open checkout redesign for review"
git push -u origin spec/checkout-redesign
```

The push triggers `spec-review.yml`:

- **notify** detects `draft → in_review` and messages approvers + commenters +
  viewers with a link.
- **gate** reports the spec isn't approved yet (advisory — it doesn't block).

When the team signs off in the docs tool, the owner records it and moves to
`approved`:

```yaml
status: approved
approved_by: [elena]
```

Push again — notify messages the **owner** "ready to build," and the gate reports
`cleared_to_build`. You then start the build yourself (nothing runs automatically).

### Rehearse without sending

To preview routing without delivering anything, run the notifier in `--dry-run`
locally after committing a status change on a spec branch:

```bash
python -m hureva.notify --dry-run \
  --event-file <(printf '{"before":"%s","after":"%s"}' "$(git rev-parse HEAD~1)" "$(git rev-parse HEAD)")
```

It prints who *would* be notified, on which channel, and needs no credentials.

---

## Step 7 — (Later) turn on enforcement

Everything above is **advisory**. To make CI actually block un-approved specs, in
`.github/workflows/spec-review.yml` add `--enforced` to the gate step:

```yaml
- run: python -m hureva.gate --changed --specs-dir specs --enforced
```

Then add **branch protection** on `main` and mark the `gate` check **required**,
so an un-approved spec can't merge. Same file, one flag.

---

## Troubleshooting

- **`pip install` fails in the Action** — the `growth-beaker/hureva` repo must be
  reachable from your Actions runner. If it's private, either make it public or
  provide a token with read access.
- **No notification fired** — notify only fires on a *status transition* on a
  `spec/**` branch. A body-only edit, or a push to `main`, fires nothing by design.
- **"name missing from roster"** — someone in a spec's roles isn't in `roster.yml`.
  The notifier reports this loudly instead of dropping them; add them.
- **Slack message never arrives** — check the scopes (`chat:write`,
  `users:read.email`), that the bot is invited to the target channel, and that the
  `slack:` handle is a member ID (`U…`) or `#channel`, not a bare `@name`.
