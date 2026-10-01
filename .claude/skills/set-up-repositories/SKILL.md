---
name: set-up-repositories
description: BA workflow step 7.0 — create the product repositories that the approved technical baseline lists but that don't exist yet, with the agreed structure, lint, format and test setup, then mark them ACTIVE (addendum D-39). Used by coding-agent; not for direct use.
user-invocable: false
---

# Step 7.0 — Repository Setup

| | |
|---|---|
| Input | `workflow/repositories.yaml` (status PLANNED, `path`); `technical/architecture/architecture.md` (*Technology Stack*, *Repository Structure*, *Testing Conventions*); the coding rules |
| Output | Each missing repository at its `path`, on its main branch, with an initial commit; `status: ACTIVE` in the catalog |
| Consumers | Every use case's acceptance tests (8.1), implementation (7), QA (8.2) and user guide (9) |

This step is shared by every use case. The orchestrator runs it once, even when several use cases reach it together.

## Procedure

1. For each repository whose `path` doesn't exist or whose status is PLANNED:
   - `git init` at its `path`, and create the main branch named in the architecture (default `main`).
   - Scaffold exactly what *Repository Structure* and *Technology Stack* say: framework, folder layout, build, lint, format. Nothing beyond that. Business code belongs to the use cases.
   - Install the test tooling from *Testing Conventions*. For the frontend this includes Playwright (`npm i -D @playwright/test`, `npx playwright install`, D-34), with one passing smoke test so the commands are proven to work.
   - Add `.gitignore`. Commit: `chore: scaffold <repo-name> (baseline ARCH)`.
   - `tools/ba catalog update REPO-… --data '{"status": "ACTIVE"}'`
2. Run each repository's build, lint and test commands once, and record the results in your summary.
3. **Don't make SA decisions.** If the baseline leaves a scaffolding choice open (a version, a package manager), stop and return it as `QUESTION FOR THE BA:` (for the SA) rather than choosing.

Use-case worktrees are created later, by the QA agent at 8.1:
`git -C <repo> worktree add <repo>-worktrees/<UC> -b ba/<UC>-<slug> main`

## Checklist

- [ ] Every repository in the catalog exists at its path and is ACTIVE.
- [ ] The build, lint and test commands of *Testing Conventions* run green on the scaffold.
- [ ] Nothing was pushed (D-25).
