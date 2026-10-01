---
name: write-user-guide
description: BA workflow Phase 9 — the end-user guide for one delivered use case, generated from the implemented application with real screenshots (ba-ai/user-guide/<UC>/guide.md). Used by documentation-agent; not for direct use.
user-invocable: false
---

# Phase 9 — User Guide

| | |
|---|---|
| Input | The running application (from the implementation summary's *How to run locally*), the approved spec (flows, messages, permissions), test results, product overview (terminology) |
| Output | `ba-ai/user-guide/<UC>/guide.md`, `ba-ai/user-guide/<UC>/screenshots/step-NN.png` |
| Consumers | The BA at GATE-08; the product's users |

## Procedure

1. **Start the application** from the use case's worktrees (`delivery.repositories[].worktree`), on a free port, with test data that shows the normal path. If it won't start, stop and report it. Never use prototype images.
2. **Walk the main flow** as the actor. For each step, capture a screenshot with Playwright from the frontend worktree (D-34): a small script at `e2e/user-guide/<uc>.spec.ts`, run with `npx playwright test e2e/user-guide/<uc>.spec.ts`, that calls `page.screenshot({ path: '<abs path>/ba-ai/user-guide/<UC>/screenshots/step-01.png' })`. Commit only that script, with `<UC>: user-guide screenshots`.
3. **Write the guide** for the actor, not for developers: short imperative instructions, using the exact labels the application shows.
   - *Common Errors*: the validation and error messages the user can meet, from the spec's VR and EF, as the application words them, each with how to fix it.
   - *Troubleshooting*: what to do when something outside the user's control fails.
4. Compare with the approved spec while you go. Report any difference; never describe behaviour the application doesn't have.
5. `tools/ba stamp ba-ai/user-guide/<UC>/guide.md` → `tools/ba validate` (it checks that every image exists).

## Template

````markdown
---
id: <UC>
artifact_type: user-guide
title: <feature name as users know it>
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
relations:
  screens: [SCR-...]
updated_at: ""
---
# <feature name>

## Purpose
<what the user achieves>

## Who Can Use This Feature
<roles, from the actors and permissions>

## Preconditions
- …

## Process Overview
<two or three sentences; optional Mermaid flow>

## Step 1 — <action>
![<what the screen shows>](screenshots/step-01.png)

<instruction>

## Step 2 — <action>
![…](screenshots/step-02.png)

<instruction>

## Expected Result
<what the user sees when done, and what happens next (e.g. who is notified)>

## Common Errors
| Message | Why | What to do |
|---|---|---|

## Troubleshooting
- …
````

## Checklist

- [ ] Every step has a screenshot of the implemented application, and the instructions use its exact labels.
- [ ] Every user-facing error from the spec is in *Common Errors*.
- [ ] Differences from the approved spec are reported, not hidden.
