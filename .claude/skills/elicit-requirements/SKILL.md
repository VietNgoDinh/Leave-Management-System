---
name: elicit-requirements
description: BA workflow Phase 2 steps 2.1–2.3 and 2.6 — understand current and future need, gap analysis, and consolidation of stakeholder material into requirements, assumptions and the elicitation summary (ba-ai/requirements/elicitation/elicitation-summary.md). Used by elicitation-agent; not for direct use.
user-invocable: false
---

# Phase 2 — Requirement Elicitation (2.1, 2.2, 2.3, 2.6)

| | |
|---|---|
| Input | Everything in `ba-ai/requirements/raw/` and `ba-ai/requirements/meetings/`; context package `ba-ai/workflow/context/ELICITATION.yaml` |
| Output | `ba-ai/requirements/elicitation/elicitation-summary.md`; `requirements/requirements.yaml` (REQ); `requirements/assumptions/assumptions.yaml` (ASM); answers on `open-questions.yaml` |
| Consumers | Overview analysis (Phase 3), the BA at GATE-02, clarification questions (2.4) |

## Procedure

1. **Read every source.** For a `.docx`, extract the text, e.g. `textutil -convert txt -stdout <file>` on macOS, or `unzip -p <file> word/document.xml | sed -e 's/<[^>]*>/ /g'`. List each source with its date and author in *Sources*.
2. **2.1 Current need (AS-IS):** the current problem, affected users, pain points, existing process, limitations, reason for change. Only what the sources say.
3. **2.2 Future need (TO-BE):** desired outcome, future process, expected user and system behaviour, business goals.
4. **2.3 Gap analysis:** a table of process, system, data, integration and policy gaps, plus *unresolved decisions*. Each unresolved decision becomes a clarification question (step 2.4, `generate-clarification-questions`).
5. **Requirements.** One REQ per distinct business need, in stakeholder language, testable later. Reuse first: `tools/ba find <keywords>`.
   `tools/ba catalog add requirements --data '{"name": "...", "description": "...", "source": "<file> §<section> (or meetings/<file>)", "priority": "HIGH"}'`
   Priority comes from the source (must/should/could). If the source gives none, use MEDIUM and say so in *Decisions* as an assumption.
6. **Assumptions.** Where a reasonable reading fills a small gap, add an assumption the BA can confirm, instead of a requirement:
   `tools/ba catalog add assumptions --data '{"statement": "...", "reason": "...", "status": "OPEN", "related": ["REQ-..."]}'`
7. **2.6 Consolidation** (action REGENERATE, new meeting notes):
   - For each open question the notes answer: `tools/ba catalog update Q-... --data '{"status": "ANSWERED", "answer": "...", "answer_source": "meetings/<file>"}'`.
   - New needs → new REQs. Changed needs → update the REQ and append the meeting to its `source`.
   - Confirmed or rejected assumptions → `status: CONFIRMED|REJECTED`.
   - Record each stakeholder decision in *Decisions*, with its source.
8. Write the summary (template below), then `tools/ba stamp ba-ai/requirements/elicitation/elicitation-summary.md` and `tools/ba validate`.

## Template

````markdown
---
id: ELICITATION
artifact_type: elicitation-summary
title: <product> — Elicitation Summary
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
open_questions: [Q-..., ...]
assumptions: [ASM-..., ...]
updated_at: ""
---
# <product> — Elicitation Summary

## Sources
| Source | Kind | Date | Author / stakeholder |
|---|---|---|---|

## Current Need
<AS-IS: problem, affected users, pain points, existing process, limitations, reason for change — cite sources>

## Future Need
<TO-BE: desired outcome, future process, expected user/system behaviour, business goals>

## Gap Analysis
| Gap | Type (process/system/data/integration/policy) | AS-IS | TO-BE | Requirement / question |
|---|---|---|---|---|

## Clarification Questions
<Open questions grouped by stakeholder; blocking ones first. IDs only — the text lives in open-questions.yaml>

## Decisions
| Decision | Source |
|---|---|

## Requirements Summary
| REQ | Name | Priority | Source |
|---|---|---|---|
````

## Checklist

- [ ] Every REQ cites a source document; none comes from your own preference.
- [ ] AS-IS and TO-BE are in separate sections (Rule 2).
- [ ] Every unresolved decision is an open question, not a requirement.
- [ ] No question is ANSWERED without an `answer_source` pointing at `raw/` or `meetings/`.
