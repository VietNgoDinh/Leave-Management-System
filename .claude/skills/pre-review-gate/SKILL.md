---
name: pre-review-gate
description: AI pre-review before a human gate (addendum D-40) — check the gate's artifacts against their inputs, the producing method skills' checklists and the gate's review focus, then record PASS or FINDINGS with `tools/ba prereview record`. Used by review-agent; not for direct use.
user-invocable: false
---

# AI pre-review of a gate

| | |
|---|---|
| Input | The brief `ba-ai/workflow/context/<SUBJECT>-<GATE>-prereview.yaml` (artifacts, their inputs, method skills, review focus, earlier findings); the use case's context package when the subject is a use case |
| Output | A verdict recorded by `tools/ba prereview record` (stored in `ba-ai/reviews/pre-review/<SUBJECT>/<GATE>.json`, hashed like a gate request) |
| Consumers | The orchestrator: FINDINGS go back to the artifact's owner, then a new round (at most 2). PASS lets the gate be requested. The human reviewer sees any findings left over. |

## Procedure

1. Read the brief. Then read, in this order:
   - the artifacts under review;
   - the inputs each was built from;
   - the *Checklist* and *Rules* of each producing method skill (`method_skills`).
2. Check each artifact:
   - **Faithful to its inputs.** Nothing contradicts an approved upstream artifact or catalog item. Nothing is added that the inputs don't support.
   - **Complete.** Every rule, VR, AF, EF and AC the inputs require is covered. Every checklist item holds.
   - **Consistent.** Messages, error codes, field names, IDs and states agree across the artifacts of this gate.
   - **No invented decisions.** Unknowns are open questions or assumptions, not silent choices.
   - **The review focus.** Each bullet the human will check: would they send it back?
3. Previous round's findings (`previous_findings`): check whether each one was addressed. Don't repeat a finding the owner explained away unless the explanation is wrong; then say why.
4. Write the findings file in `ba-ai/workflow/context/<SUBJECT>-<GATE>-findings.yaml`:
   ```yaml
   findings:
     - artifact: ba-ai/specifications/analysis/UC-007-activity.md
       severity: MAJOR          # MAJOR: the reviewer would send it back · MINOR: could be approved as is
       issue: "UC-007-VR-03 says 422 OVERLAP; the API design returns 409 BOOKING_CONFLICT for the same check"
       suggestion: "Align with the API design (technical/api/UC-007.md, API-012 errors)"
   ```
   `artifact` must be one of the gate's artifacts. Name the precise place: ID, section or line.
5. Record:
   - `tools/ba prereview record <GATE> <SUBJECT> --verdict FINDINGS --file ba-ai/workflow/context/<SUBJECT>-<GATE>-findings.yaml`
   - or, with no MAJOR finding: `--verdict PASS`, with the file only if you have MINOR notes.

## Checklist

- [ ] Every finding is specific (artifact + ID/section) and says why it matters.
- [ ] No style-only findings; MINOR is used only for things the reviewer could accept as they are.
- [ ] Nothing was edited; the verdict was recorded with the CLI.
