---
name: ba-approve
description: Human approval of a BA workflow gate. Typed by the user only.
argument-hint: "<SUBJECT> <GATE-ID> [comment]"
disable-model-invocation: true
---

The user typed: `/ba-approve $ARGUMENTS`

The `UserPromptSubmit` hook records this decision **before** you see this message. You never record gate decisions yourself (CLAUDE.md, hard rule 1).

1. Look for the `[BA gate hook] Recorded APPROVED …` line in your context. Confirm it with `tools/ba gate status <SUBJECT>`: the gate must show APPROVED.
2. **Not recorded** (no hook line, or the gate isn't APPROVED): tell the user the approval was *not* recorded. Explain the likely reason (hooks load when Claude Code starts, so a restart may be needed) and give the fallback they can run in their own terminal:
   `tools/ba decide approve <SUBJECT> <GATE-ID> "<comment>"`
   Then stop. Don't try to record it any other way.
3. **Recorded:** run `tools/ba sync`, then continue with the **Orchestrator procedure** in `CLAUDE.md`. If the subject is a use case, the scope is that use case. If it is a run, the scope is the whole run.
