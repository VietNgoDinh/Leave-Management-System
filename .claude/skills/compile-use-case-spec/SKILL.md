---
name: compile-use-case-spec
description: BA Spec Engine step 5.8 — compile the UI, sequence, API, validation and acceptance artifacts into one code-ready use-case specification (ba-ai/specifications/use-cases/<UC>.md). Used by spec-agent; not for direct use.
user-invocable: false
---

# Step 5.8 — Compile Code-Ready BA Specification

| | |
|---|---|
| Input | All six upstream artifacts for the use case + context package |
| Output | `ba-ai/specifications/use-cases/<UC>.md` |
| Consumers | BA approval (GATE-05) → SA review (GATE-06) → coding agent, QA |

## Rules

- **Compile, don't create.** Every statement comes from an upstream artifact or the context package. New behaviour is never introduced here.
- **Conflicts are surfaced, not resolved.** If two upstream artifacts disagree (a message text, an error code, a field rule), don't pick one. Add an open question, list it in section 19, and tell the orchestrator in your summary which artifact needs fixing.
- The spec must be readable on its own by a developer: condense, but keep every field, rule, validation, API, status code and acceptance criterion.
- Use the exact 20 section headings below (numbered as shown).
- `relations` and `open_questions` are the union of the upstream artifacts'.
- Section 14 contains the main-flow Mermaid diagram. Section 15 summarises each API and links to `technical/api/<UC>.md` for full request/response schemas.
- Section 20 is a traceability table. Every AC appears in it.

## Template

````markdown
---
id: <UC>
artifact_type: use-case-specification
title: <use case name>
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
relations:
  business_process: [<BP>]
  requirements: [<REQ>, ...]
  business_rules: [<BR>, ...]
  entities_read: [<ENT>, ...]
  entities_written: [<ENT>, ...]
  screens: [<SCR>, ...]
  apis: [<API>, ...]
open_questions: []
assumptions: []
updated_at: ""
---
# <UC> — <use case name>

## 1. Objective
## 2. Actor
## 3. Preconditions
## 4. Trigger
## 5. Business Context
Process step (BP-…-S…), requirements, why this matters.
## 6. User Flow
Short numbered user journey across screens.
## 7. UI Specification
Per screen: fields, actions, states, messages (condensed from the UI markdown; link the prototype).
## 8. Main Flow
Numbered system-level steps (actor action → system response).
## 9. Alternate Flows
<UC>-AF-… from the activity analysis.
## 10. Error Flows
<UC>-EF-….
## 11. Business Rules
Each BR with its full text and how it applies here.
## 12. Validation Rules
<UC>-VR-… table: check, rule, where, message/code.
## 13. Data Entities
Entities read/written, attributes touched, state transitions.
## 14. Sequence Diagram
```mermaid
sequenceDiagram
```
## 15. API Specification
| API | Method | Endpoint | Purpose | Key errors |
## 16. Acceptance Criteria
All <UC>-AC-… (Given/When/Then kept).
## 17. Dependencies
Other use cases, integrations, open technical decisions.
## 18. Assumptions
## 19. Open Questions
## 20. Traceability
| Requirement | Process step | Rules | Screens | APIs | Entities | Acceptance criteria |
|---|---|---|---|---|---|---|
````
