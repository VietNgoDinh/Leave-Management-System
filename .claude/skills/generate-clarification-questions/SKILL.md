---
name: generate-clarification-questions
description: BA workflow Phase 2 step 2.4 — clarification questions grouped by stakeholder, each with reason, impact, priority and whether it blocks the overview (ba-ai/requirements/clarification-log/open-questions.yaml). Used by elicitation-agent; not for direct use.
user-invocable: false
---

# Step 2.4 — Generate Clarification Questions

| | |
|---|---|
| Input | Gap analysis and unresolved decisions from step 2.3; existing open questions |
| Output | Items in `ba-ai/requirements/clarification-log/open-questions.yaml` (Q-NNN) |
| Consumers | The BA's stakeholder meetings (step 2.5), the orchestrator's stakeholder wait, overview analysis |

## Procedure

1. Read the existing questions first (`tools/ba catalog list open-questions`, `tools/ba find <keywords>`). Never ask the same thing twice. Sharpen an existing question with `catalog update` instead.
2. One question per decision. Ask it so a stakeholder can answer it in one sentence, and offer the options you see when there are some.
3. Add it:
   ```
   tools/ba catalog add open-questions --data '{
     "question": "...", "reason": "why the material does not settle it",
     "impact_if_unanswered": "what cannot be specified, or would be guessed",
     "target_stakeholder": "BUSINESS", "priority": "HIGH", "status": "OPEN",
     "blocking": true, "related": ["REQ-..."]}'
   ```
   - `target_stakeholder`: BUSINESS, OPERATIONS, SECURITY, DATA, INTEGRATION, COMPLIANCE, TECHNICAL or UX.
   - `priority`: HIGH when it changes scope, a process or the data model; MEDIUM for a rule or behaviour; LOW for wording and presentation.
4. **`blocking: true` only** when the overview cannot be written responsibly without the answer:
   - scope or boundary;
   - who the actors are;
   - a core process path;
   - a data-model choice;
   - a hard policy.
   While a blocking question is OPEN, the workflow stops and waits for stakeholders (master §8 step 2.5). Everything else gets `blocking: false`. It travels on as an open question and is resolved at the BA reviews.
5. List the new IDs in the summary's *Clarification Questions*, grouped by stakeholder, blocking ones first.

## Checklist

- [ ] Each question has reason, impact, stakeholder, priority, status and `blocking`.
- [ ] No question answers itself, and none is a disguised decision ("Should we use X?" when the material already says X).
- [ ] `blocking` is used sparingly. A long list of blocking questions means the scope is unclear; say so in your summary.
