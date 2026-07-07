# Working with specs in this repo

This repo uses the **spec review & approval workflow**: specs live here alongside
the code. When you generate a spec, follow these rules so it flows through review
and the gate unchanged. (This guidance is tool-neutral — it does not require
superpowers.)

## Where specs live

- Specs live under `specs/<feature-slug>/spec.md`.
- The team roster is `specs/roster.yml`; default roles are `specs/defaults.yml`.

## How to create a spec

Prefer the one-step command:

```
/new-spec <slug> "Feature title"
```

or run it directly:

```
hureva-new-spec <slug> --title "Feature title"
```

Either seeds roles from `defaults.yml`, writes `specs/<slug>/spec.md`, and creates
a `spec/<slug>` branch. Author by hand from `specs/spec.template.md` if you prefer.

## Frontmatter schema (the runtime contract, §4.2)

```yaml
title: string
status: draft | in_review | approved | implemented | archived
owner: <roster key>
approvers: [<roster key>, ...]   # may sign off
commenters: [<roster key>, ...]  # may comment, not approve
viewers: [<roster key>, ...]     # read-only
approved_by: [<roster key>, ...] # subset of approvers
approved_at: date | null
version: "semver-ish"
```

All people are **roster keys** (names only) — never inline emails or Slack
handles. Seed unset roles from `defaults.yml`; override per spec as needed.

## Lifecycle

`draft -> in_review -> approved -> implemented` (plus `archived`). Pushing a spec
with `status: in_review` onto its `spec/<slug>` branch opens it for review and
notifies the reviewers. Move to `approved` only after the team signs off; the
owner records `approved_by`. Do **not** start the build until `status: approved`.
