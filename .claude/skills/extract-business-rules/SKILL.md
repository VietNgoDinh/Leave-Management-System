---
name: extract-business-rules
description: BA workflow Phase 3 step 3.3 — business rules with stable BR IDs, each traced to its source requirement, entities and use cases (ba-ai/overview/business-rules.yaml). Used by overview-analysis-agent; not for direct use.
user-invocable: false
---

# Step 3.3 — Business Rules

| | |
|---|---|
| Input | Requirements, elicitation summary (decisions), the data model |
| Output | `overview/business-rules.yaml` (BR) |
| Consumers | The BA at GATE-02, UI validations (5.2), validation analysis (5.6, every VR cites a BR), acceptance criteria (5.7), QA (8.1) |

## Procedure

1. A business rule is a constraint or a calculation the business imposes: eligibility, limits, deadlines, approvals, calculations, visibility. It is not a UI preference or a technical choice.
2. One rule per constraint, stated so it can be tested: who, when, what limit, and what happens on violation.
3. Reuse first (`tools/ba find <keywords>`), then:
   ```
   tools/ba catalog add business-rules --data '{
     "name": "Leave only on working days", "description": "...testable statement...",
     "source": "REQ-003 (URS §4.1)", "applies_to": "Leave Request submission",
     "requirements": ["REQ-003"], "related_entities": ["ENT-005"]}'
   ```
   Add `related_use_cases` once the use cases exist (`define-use-cases` links them back).
4. A rule the material implies but doesn't settle (the limit value, the exception, the violation behaviour) gets recorded with the known part. The unknown part becomes an open question related to the BR (BUSINESS, or COMPLIANCE for regulatory rules).
5. Never merge two rules because they share a sentence in the source. Never split one rule into several because it has several examples.

## Checklist

- [ ] Every rule cites a REQ or a recorded stakeholder decision in `source`.
- [ ] Every rule names what happens on violation (block, warn, flag for review), or has an open question for it.
- [ ] No technical or UI rule here. Those belong in the baseline or the screen design.
