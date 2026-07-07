---
description: Scaffold a new spec folder, seed roles from defaults.yml, and create its spec/<slug> branch.
argument-hint: <slug> "<Feature title>"
---

Create a new spec for `$ARGUMENTS`.

Run the command below, which reads `specs/defaults.yml`, seeds the frontmatter
roles, writes `specs/<slug>/spec.md` from the template, and creates a
`spec/<slug>` git branch:

```
hureva-new-spec <slug> --title "<Feature title>"
```

Then draft the spec body with the user. Leave `status: draft` until they are ready
to open it for review; when they are, set `status: in_review` and push the
`spec/<slug>` branch — that notifies the reviewers.
