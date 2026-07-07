# Installing hureva in your team's repo

Your specs live in your own repo under `specs/`. You install hureva by
**referencing** it — you don't copy its code. Concretely you add: one small caller
workflow, a bit of config, and a Slack secret. hureva itself (its reusable workflow
and its Python package) stays in the hureva project and is pulled in at run time.

Reviewers (PM/UX/QA) install **nothing** — they review in GitBook/ReadMe in a
browser.

---

## How the install works (the 30-second version)

hureva ships as two referenced pieces:

- a **reusable GitHub Actions workflow** — you point at it with one `uses:` line;
- a **PyPI package** (`hureva`) — the reusable workflow `pip install`s it to do the work.

Your repo gets a caller workflow like this:

```yaml
# your-repo/.github/workflows/spec-review.yml
on:
  push:
    branches: ["spec/**"]
    paths: ["specs/**"]
jobs:
  spec-review:
    uses: growth-beaker/hureva/.github/workflows/spec-review.yml@v1
    with: { specs_dir: specs }
    secrets: inherit
```

### What does `@v1` mean?

`uses: growth-beaker/hureva/.github/workflows/spec-review.yml@v1` says: **"run
hureva's `spec-review.yml`, at the version tagged `v1`."** It's a *version pin*,
just like `"hureva": "^1.0"` in a dependency list.

- At push time GitHub fetches that workflow **at `v1`** and runs it against your
  repo (your specs, your secrets). Nothing of hureva's is stored in your repo.
- Pinning `@v1` means your setup behaves the same forever; when hureva ships `v2`
  it does **nothing** to you until you change that one line to `@v2`. You upgrade
  on your schedule.

This is the opposite of copying hureva's code in (which would drift and never get
fixes). You reference a released version and opt into upgrades.

---

## Step 1 — Add the caller workflow

Create `.github/workflows/spec-review.yml` in your repo with the YAML above.

- **Specs elsewhere?** If you keep specs under, say, `docs/specs`, set both the
  `paths:` filter and `with: { specs_dir: docs/specs }` to match. (The `paths:`
  value must be a literal — GitHub Actions can't use a variable there.)
- **Enforce later:** add `enforced: true` under `with:` when you want CI to block
  un-approved specs (Step 7). Start without it.

---

## Step 2 — Add your config

Two files under `specs/` (or your chosen path). Everything references people by
**roster key** (short name), never by inline email/Slack.

`specs/roster.yml` — the only place channels are defined:

```yaml
people:
  chris:   { email: chris@acme.com, slack: "U01ABC123" }  # Slack member ID
  elena:   { email: elena@acme.com, slack: "U02DEF456" }
  sam:     { email: sam@acme.com }                         # email only is fine
  qa-team: { slack: "#qa" }                                # a channel is fine
```

- **Channel choice:** Slack is used if `slack:` is present, otherwise email.
- **Reliable Slack delivery:** use a **member ID** (`U…`, from a person's Slack
  profile → "Copy member ID") for DMs, or a `#channel` for groups. A bare
  `@username` is not reliable. (You can also put an **email** in `slack:` and the
  bot DMs the matching user via `users.lookupByEmail`.)

`specs/defaults.yml` — copied into each **new** spec at creation, overridable per spec:

```yaml
owner: chris
approvers: [elena]
commenters: [sam]
viewers: [qa-team]
```

*(Optional authoring aids: copy `CLAUDE.md`, `specs/spec.template.md`, and
`.claude/commands/new-spec.md` from the hureva repo if you want the `/new-spec`
command and Claude guidance. They're conveniences, not required.)*

---

## Step 3 — Create a Slack app and add the token as a secret

1. <https://api.slack.com/apps> → **Create New App** → *From scratch* → your workspace.
2. **OAuth & Permissions → Bot Token Scopes**: add `chat:write` and `users:read.email`.
3. **Install to Workspace**, copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Invite the bot** to any channel you use as a roster target (`/invite @your-bot`).
5. In your repo: **Settings → Secrets and variables → Actions → New repository
   secret** → name `SLACK_BOT_TOKEN`, paste the token.

`secrets: inherit` in the caller forwards it to hureva's workflow. A channel is
used only if its secret is set, so a Slack-only team sets just `SLACK_BOT_TOKEN`.

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
git commit -m "Add spec review & approval (references hureva@v1)"
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

The push triggers your caller → hureva's reusable workflow:

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
python -m hureva.notify --dry-run \
  --event-file <(printf '{"before":"%s","after":"%s"}' "$(git rev-parse HEAD~1)" "$(git rev-parse HEAD)")
```

---

## Step 7 — (Later) turn on enforcement

Everything above is **advisory**. To make CI block un-approved specs, add
`enforced: true` to your caller:

```yaml
  spec-review:
    uses: growth-beaker/hureva/.github/workflows/spec-review.yml@v1
    with:
      specs_dir: specs
      enforced: true
    secrets: inherit
```

Then add **branch protection** on `main` and mark the gate check **required**, so
an un-approved spec can't merge. Same one line of config.

---

## Upgrading hureva

When hureva releases a new major version, bump the pin in your caller
(`@v1` → `@v2`) when you're ready; read its release notes first. Patch and minor
fixes inside the 1.x line flow in automatically because the reusable workflow
installs `hureva~=1.0`. To freeze the library exactly, pass
`with: { hureva_version: "==1.2.3" }`.

---

## Troubleshooting

- **`uses: … @v1` can't be found** — the `growth-beaker/hureva` repo must be
  visible to your Actions. Public repos work out of the box; for a private hureva,
  enable org access to its workflows.
- **`pip install hureva` fails in the run** — hureva must be published to PyPI for
  the version your `@v1` resolves to. Until the first release, install from git by
  setting `hureva_version` to ` @ git+https://github.com/growth-beaker/hureva.git@v1`
  (note the leading space — it becomes `pip install "hureva @ git+…"`).
- **No notification fired** — notify only fires on a *status transition* on a
  `spec/**` branch. A body-only edit, or a push to `main`, fires nothing by design.
- **"name missing from roster"** — someone in a spec's roles isn't in `roster.yml`.
  The notifier reports this loudly instead of dropping them; add them.
- **Slack message never arrives** — check the scopes (`chat:write`,
  `users:read.email`), that the bot is invited to the target channel, and that the
  `slack:` handle is a member ID (`U…`) or `#channel`, not a bare `@name`.
