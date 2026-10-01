---
name: compile-use-case-spec
description: BA Spec Engine step 5.8 — assemble the code-ready use-case specification with `tools/ba compile` and write its narrative sections (ba-ai/specifications/use-cases/<UC>.md). Used by spec-agent; not for direct use.
user-invocable: false
---

# Step 5.8 — Compile Code-Ready BA Specification

| | |
|---|---|
| Input | All six upstream artifacts for the use case + context package |
| Output | `ba-ai/specifications/use-cases/<UC>.md` |
| Consumers | BA approval (GATE-05) → SA review (GATE-06) → acceptance tests (8.1), coding agent, QA |

## How it is built (D-43)

`tools/ba compile <UC>` assembles the 20-section document.
- **13 sections are generated** from their sources, verbatim or as a table: 2 Actor, 7 UI Specification, 9 Alternate Flows, 10 Error Flows, 11 Business Rules, 12 Validation Rules, 13 Data Entities, 14 Sequence Diagram, 15 API Specification, 16 Acceptance Criteria, 18 Assumptions, 19 Open Questions, 20 Traceability.
- Copying is done by the tool rather than by you, so the spec can never drift from what was reviewed upstream.
- `tools/ba validate` rejects any hand edit to these sections.
- **You write the 7 narrative sections**: 1 Objective, 3 Preconditions, 4 Trigger, 5 Business Context, 6 User Flow, 8 Main Flow, 17 Dependencies. Each starts with a `<!-- TODO(spec-agent): … -->` hint. Replace the whole hint with the text.

## Procedure

1. `tools/ba stamp ba-ai/specifications/analysis/<UC>-acceptance.md` (if not done), then `tools/ba compile <UC>`.
2. Write each narrative section from the upstream artifacts and the context package:
   - **Compile, don't create.** Every statement comes from an upstream artifact or the context package. New behaviour is never introduced here.
   - 8 Main Flow: numbered steps "actor action → system response", consistent with the sequence (section 14) and the UI (section 7).
   - Keep them short. The generated sections carry the detail, and a developer reads both.
   - A section that doesn't apply to this use case says "Not applicable." with a few words of why.
3. **Conflicts are surfaced, not resolved.** If two upstream artifacts disagree (a message text, an error code, a field rule), don't pick one. Add an open question and tell the orchestrator in your summary which artifact needs fixing. The generated sections show both versions, because they copy them.
4. `tools/ba stamp ba-ai/specifications/use-cases/<UC>.md` → `tools/ba validate`.

**REGENERATE** (an upstream artifact changed): run `tools/ba compile <UC>` again. It refreshes the generated sections and keeps your narrative. Then update only the narrative sentences the change affects, and stamp.

## Checklist

- [ ] No TODO hint is left; no generated section was edited by hand.
- [ ] Every narrative statement traces to an upstream artifact or the context package.
- [ ] Conflicts between upstream artifacts are open questions and are reported, not silently resolved.
