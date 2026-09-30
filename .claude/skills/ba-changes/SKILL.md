---
name: ba-changes
description: Human request for changes at a BA workflow gate, with comments. Typed by the user only.
argument-hint: "<SUBJECT> <GATE-ID> <what to change>"
disable-model-invocation: true
---

The user typed: `/ba-changes $ARGUMENTS`

The `UserPromptSubmit` hook records this decision and the comments **before** you see this message. You never record gate decisions yourself (CLAUDE.md, hard rule 1).

1. Look for the `[BA gate hook] Recorded CHANGES_REQUESTED …` line in your context. Confirm it with `tools/ba gate status <SUBJECT>`: the gate must show CHANGES_REQUESTED.
2. **Not recorded:** tell the user the request was *not* recorded. Explain the likely reason (hooks load when Claude Code starts, so a restart may be needed) and give the fallback for their own terminal:
   `tools/ba decide changes <SUBJECT> <GATE-ID> "<comments>"`
   Then stop.
3. **Recorded:** run `tools/ba sync`, then follow the **Orchestrator procedure** in `CLAUDE.md` for this subject. `tools/ba next` returns a REVISE action carrying the comments. Handle it as described under *Review feedback*: change only what the comments require, then request the gate again.
