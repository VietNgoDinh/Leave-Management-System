---
name: plan-backlog
description: BA workflow Phase 4 — group the approved use cases into epics with priorities, dependencies and readiness, and write the delivery backlog through `tools/ba backlog plan` (ba-ai/planning/backlog.yaml). Used by planning-agent; not for direct use.
user-invocable: false
---

# Phase 4 — BA Planning (delivery backlog)

| | |
|---|---|
| Input | Context package `PLANNING.yaml`: the use cases (with process, actor, application, complexity, risk), requirements and their priorities, open questions, the current backlog |
| Output | `planning/backlog.yaml` — written only by `tools/ba backlog plan --file <plan>` |
| Consumers | `tools/ba next` (what to specify next, in priority order), `/ba-spec`, the BA (who adjusts priority, status and dependencies) |

## Procedure

1. **Epics.** Group the use cases by the business capability they deliver, usually one business process or one coherent part of it. An epic should be deliverable and demonstrable on its own.
2. **Priority** (HIGH / MEDIUM / LOW) for each epic and each use case comes from the priorities of the requirements it satisfies: the highest one wins. Ties are broken by dependency order. Don't invent a business priority. If the requirements don't separate two epics, keep them equal and say so.
3. **Dependencies.** UC-B depends on UC-A when B's specification needs A's approved screens, APIs or data. For example, "modify a request" depends on "submit a request". The spec engine starts B only after A's GATE-05. Keep the list minimal; the tool rejects cycles.
4. **Readiness**, as a proposal the BA can change in the YAML:
   - `READY` — the use case can be specified now.
   - `BACKLOG` — not yet. Its HIGH open questions are unanswered, or it's deliberately later. Give the reason in your summary.
   - `BLOCKED`, with `blocked_reason` — something outside the BA's control stops it.
5. **Write the plan** to `ba-ai/workflow/context/PLANNING-plan.yaml`:
   ```yaml
   epics:
     - name: Leave request lifecycle        # omit epic_id for a new epic; keep it for an existing one
       priority: HIGH
       description: Employees request leave; managers confirm and approve.
       use_cases:
         - {use_case_id: UC-001, priority: HIGH, status: READY, dependencies: []}
         - {use_case_id: UC-003, priority: MEDIUM, status: READY, dependencies: [UC-001]}
   ```
   Then run `tools/ba backlog plan --file ba-ai/workflow/context/PLANNING-plan.yaml`.
   - Every use case in the catalog must appear exactly once.
   - On a re-plan, copy the current entries from the context package: started use cases keep their status (the tool never undoes progress), and existing epics keep their `epic_id`.
6. Read the result with `tools/ba status`.

## Checklist

- [ ] Every catalog use case is in exactly one epic.
- [ ] Priorities trace to requirement priorities; dependencies follow data and screen reuse.
- [ ] Every `BACKLOG` use case has its reason stated in your summary.
