---
name: define-use-cases
description: BA workflow Phase 3 step 3.6 — the use-case list with process, actor, application, complexity, risk (D-23), requirements, rules and entities, plus the links back from processes and rules (ba-ai/overview/use-cases.yaml). Used by overview-analysis-agent; not for direct use.
user-invocable: false
---

# Step 3.6 — Use Case List

| | |
|---|---|
| Input | Processes, rules, data model, actors, applications, requirements |
| Output | `overview/use-cases.yaml` (UC); `related_use_cases` on rules; `use_cases` on process steps |
| Consumers | The BA at GATE-02, planning (Phase 4), the Spec Engine (every context package), GATE-07 (risk) |

## Procedure

1. One use case per goal an actor achieves in one sitting, or one system job ("cancel unreviewed requests at month end", actor = the scheduler). Name it verb + object.
2. Reuse first (`tools/ba find <keywords>`), then:
   ```
   tools/ba catalog add use-cases --data '{
     "name": "Submit leave request", "business_process": "BP-001", "actor": "ACT-001",
     "application": "APP-001", "description": "<goal, main path, key variations, outcome>",
     "complexity": "HIGH", "risk_level": "MEDIUM", "risk_flags": [],
     "requirements": ["REQ-001"], "business_rules": ["BR-001", "BR-002"],
     "entities_read": ["ENT-002"], "entities_written": ["ENT-005"]}'
   ```
3. **Complexity** is LOW, MEDIUM or HIGH: number of screens, rules and branches, and integrations.
4. **Risk** (D-23) is a *proposal* that the BA confirms at GATE-02:
   - `risk_level` LOW / MEDIUM / HIGH / CRITICAL;
   - `risk_flags`, any of FINANCIAL, IRREVERSIBLE, SECURITY, COMPLIANCE, PERSONAL_DATA. Set a flag only when the use case really moves money, can't be undone, changes access, falls under regulation, or processes personal data.
   - HIGH, CRITICAL or any flag makes a human critical-flow test (GATE-07) mandatory after QA. Explain each flag in the description.
5. **Link back:**
   - each rule's `related_use_cases`: `tools/ba catalog update BR-... --data '{"related_use_cases": [...]}'`. The list is replaced, so repeat the existing values.
   - each process step's `use_cases` (see `model-business-processes`).
6. **Coverage check**, before returning:
   - every REQ is satisfied by at least one UC;
   - every BR is used by at least one UC;
   - every process step that an actor performs has a UC.
   Report the gaps. A gap is an open question, not a new invented use case.

## Checklist

- [ ] Every UC has process, actor, application, description, complexity, risk_level and requirements.
- [ ] Rules and entities are listed on the UC and linked back.
- [ ] Risk flags are justified in the description. The BA confirms them at GATE-02.
