---
name: design-api
description: BA Spec Engine step 5.5 — specify every API the use case needs (reused, modified, new) from the sequence flow (ba-ai/technical/api/<UC>.md). Used by technical-analysis-agent; not for direct use.
user-invocable: false
---

# Step 5.5 — API Analysis and Design

| | |
|---|---|
| Input | `ba-ai/technical/sequence/<UC>.md`, API conventions in `technical/architecture/architecture.md`, `technical/security/security-rules.md`, `technical/api/api-catalog.yaml`, context package |
| Output | `ba-ai/technical/api/<UC>.md`; catalog entries; screens' `apis` updated |
| Consumers | Validation analysis (5.6), acceptance criteria (5.7), compiled spec (5.8), SA review (GATE-06) |

## Procedure

1. Take each API ID in the sequence. It must already be in the catalog (step 5.4 registered it).
2. Specify it with the YAML block in the template. Follow the API conventions exactly: paths, casing, pagination, status codes, error body, all-or-nothing behaviour for multi-item operations.
3. Authentication and authorization come from the security rules. Every validation names the rule it enforces (BR-xxx) and the error it returns.
4. **An API is defined in full once.** The use case that introduces or modifies it holds the full definition. Other use cases list it in the summary and write "defined in technical/api/<other UC>.md".
5. Link screens to APIs: `tools/ba catalog update SCR-00x --data '{"apis": ["API-00a", "API-00b"]}'` (list replaces).
6. **Don't make SA decisions.** Anything needing an architect (caching, pagination limits beyond the conventions, an external system's real endpoint, idempotency keys) goes under *Unresolved Technical Decisions* as an open question with `target_stakeholder: TECHNICAL`.

## Template

````markdown
---
id: <UC>
artifact_type: api-design
title: <use case name> — API Design
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
relations:
  apis: [<API>, ...]
  business_rules: [<BR>, ...]
  entities_read: [<ENT>, ...]
  entities_written: [<ENT>, ...]
  screens: [<SCR>, ...]
open_questions: []
updated_at: ""
---
# <UC> — <use case name>: API Design

## API Summary
| API | Method | Endpoint | Change | Purpose | Called from |
|---|---|---|---|---|---|

## API Details

### <API> — <METHOD> <endpoint>
```yaml
api_id: <API>
method: POST
endpoint: /api/v1/...
purpose: ...
caller: <SCR> (<APP>)
service: <SVC>
authentication: ...
authorization: ...            # cite the rule, e.g. role IT_ASSET_MANAGER (BR-006)
request:
  body: {}                    # field: type, required, constraints
response:
  "201": {}
validation:
  - "field — constraint (BR-…) → 422 CODE"
business_rules: [<BR>]
entities: {reads: [<ENT>], writes: [<ENT>]}
errors:
  - {status: 409, code: CODE, when: "...", rule: <BR>}
downstream_calls: []          # other APIs or integrations (INT-…)
```

## Unresolved Technical Decisions
- <Q-ID> — decision needed from SA/Developer (or "None")
````
