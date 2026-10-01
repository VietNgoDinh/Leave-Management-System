---
name: model-business-processes
description: BA workflow Phase 3 step 3.2 — TO-BE business processes with objective, actors, trigger and steps, each step linked to the use cases it triggers (ba-ai/overview/business-processes.yaml). Used by overview-analysis-agent; not for direct use.
user-invocable: false
---

# Step 3.2 — Business Processes

| | |
|---|---|
| Input | Future need and gap analysis from the elicitation summary, requirements, actors |
| Output | `overview/business-processes.yaml` (BP, with steps `<BP>-S01`, …) |
| Consumers | The BA at GATE-02; use cases (3.6, each belongs to a process); the graph (`ProcessStep TRIGGERS UseCase`); context packages (5.1) |

## Procedure

1. A process is an end-to-end business flow with a trigger and an outcome. "Leave request and approval" is a process; "submit leave request" is a use case inside it.
2. Add the process with its steps. Leave out step IDs, and the tool numbers them `<BP>-S01`, `-S02`, …:
   ```
   tools/ba catalog add business-processes --data '{
     "name": "...", "objective": "...", "actors": ["ACT-..."], "trigger": "...",
     "steps": [{"name": "Employee submits the request", "actor": "ACT-001"},
               {"name": "Project Manager confirms", "actor": "ACT-002"}]}'
   ```
3. Branches and exceptions are described in the step `name` or a `description`, e.g. "auto-confirmed when the requester is the Project Manager". They aren't separate processes.
4. **After the use cases exist**, link each step to the use cases it triggers, and set `related_use_cases`. The `steps` list is replaced, so repeat every step with its existing ID:
   `tools/ba catalog update BP-001 --data '{"steps": [{"id": "BP-001-S01", "name": "...", "actor": "ACT-001", "use_cases": ["UC-001"]}, …], "related_use_cases": ["UC-001", …]}'`
5. Present the flow as a Mermaid flowchart in the product overview's *High-Level Behavior* when it has more than three steps or any branch.

## Checklist

- [ ] Every process has a trigger, actors, an objective and ordered steps.
- [ ] Every step names its actor, and every step that a user or system performs is linked to a use case.
- [ ] TO-BE only. The current process belongs in the elicitation summary's *Current Need*.
