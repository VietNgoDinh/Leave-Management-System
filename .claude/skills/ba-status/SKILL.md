---
name: ba-status
description: Show where the BA workflow stands — runs, gates waiting for human review, backlog progress, stale artifacts, open questions. Use when the user asks for workflow status or progress.
---

1. Run `tools/ba sync`, then `tools/ba status`.
2. Summarise for the user in a few lines:
   - what the workflow is doing or waiting for;
   - any gate waiting for them, with the exact `/ba-approve …` / `/ba-changes …` commands;
   - blocked use cases and why;
   - stale artifacts and validation errors, if any.
   Link files as `[name](ba-ai/…)`.
3. Don't start any work. If there is work to do, say that `/ba-next` continues it.
