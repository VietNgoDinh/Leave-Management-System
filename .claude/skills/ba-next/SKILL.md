---
name: ba-next
description: Resume the BA workflow exactly where it stopped and run until the next human gate. Use when the user asks to continue or resume the BA workflow.
argument-hint: "[UC-ID | EPIC-ID]"
---

Resume the BA workflow.

Scope: `$ARGUMENTS`. When it is empty, the scope is everything actionable in the active run.

Follow the **Orchestrator procedure** in `CLAUDE.md` with this scope. Position always comes from `tools/ba next` (derived from artifacts and gates), never from memory of this conversation.
