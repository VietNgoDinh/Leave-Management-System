---
name: ba-spec
description: Run the BA Specification Engine (master spec Phase 5) — functional UI, prototype, sequence, API, validation, acceptance criteria and compiled spec — for a use case or an epic.
argument-hint: "[UC-ID | EPIC-ID]"
---

Run the BA Specification Engine. Argument: `$ARGUMENTS`

## Choose the scope (master spec §11)

1. Run `tools/ba sync`, then `tools/ba next --json`.
2. Pick the scope:
   - **No argument:** the single highest-priority use case that has an ACTION. The JSON list is already in priority order, so take the first `use_cases` entry with `"state": "ACTION"`. If none has an action, report what is waiting or blocked and stop.
   - **UC-ID:** only that use case.
   - **EPIC-ID:** every use case of the epic that has an ACTION. Independent use cases run in parallel.
3. If the run itself has a `run_action` (for example GATE-02 is not approved yet), handle that first. The spec engine can't start before it.

## Run

Follow the **Orchestrator procedure** in `CLAUDE.md`, restricted to the chosen scope.
