---
name: build-data-model
description: BA workflow Phase 3 steps 3.4 and 3.5 — the data model (entities, attributes, identifiers, relationships, cardinality, ownership) with each stateful entity's lifecycle as its state model (ba-ai/overview/data-model/entities.yaml). Used by overview-analysis-agent; not for direct use.
user-invocable: false
---

# Steps 3.4 and 3.5 — Data Model and State Model

| | |
|---|---|
| Input | Requirements, elicitation summary, actors, applications |
| Output | `overview/data-model/entities.yaml` (ENT); each stateful entity's `lifecycle` |
| Consumers | **The BA at GATE-02 — a mandatory review artifact**; UI fields (5.2), API design (5.5), validation (5.6), QA state-transition tests (8.1) |

## Procedure

1. Find the business nouns in the requirements: things that are created, changed, approved or counted. Each becomes an entity. Its `name` is the business term, and its ID comes from the tool (D-14).
2. Reuse first: `tools/ba find <noun>`. Then add:
   ```
   tools/ba catalog add entities --data '{
     "name": "Leave Request", "description": "...", "owner": "<application or external system that owns it>",
     "attributes": [{"name": "request_id", "type": "identifier"},
                    {"name": "start_date", "type": "date", "description": "..."}],
     "relationships": [{"to": "ENT-002", "cardinality": "N:1", "description": "requested by"}]}'
   ```
   - **Attributes**: name, type (identifier, string, text, integer, decimal, date, datetime, boolean, enum, reference, file) and a description where the meaning isn't obvious. Mark the identifier. Use only attributes the material implies. A plausible but unsupported attribute becomes an open question (DATA).
   - **Relationships**: `to` an existing ENT, with cardinality `1:1`, `1:N`, `N:1` or `N:M`, and a description that reads as a sentence.
   - **Ownership**: the system of record. A copy of data owned elsewhere is still an entity, with that system as owner. Say so in the description.
3. **State model (3.4)**, for every entity with a status:
   ```
   tools/ba catalog update ENT-... --data '{"lifecycle": {
     "states": ["DRAFT", "SUBMITTED", "APPROVED"],
     "transitions": ["(new) -> DRAFT: employee starts a request",
                     "DRAFT -> SUBMITTED: employee submits"],
     "invalid_transitions": ["APPROVED -> DRAFT: an approved request cannot be edited"]}}'
   ```
   - Every transition reads `FROM -> TO: triggering event` (`(new)` for creation).
   - The validator rejects states that aren't listed.
   - Name who or what triggers each transition.
   - List the transitions the business forbids, because QA tests them.
   - An unclear transition is an open question, never a guess.
4. After the rules and use cases exist, check that every entity is read or written by at least one use case. An orphan entity is either out of scope (remove it) or a missing use case (an open question).

## Checklist

- [ ] Each entity has an identifier, an owner and attributes, and every relationship has a cardinality.
- [ ] Each stateful entity has a lifecycle with transitions and invalid transitions.
- [ ] No attribute, state or relationship is invented. The unsupported ones are open questions.
