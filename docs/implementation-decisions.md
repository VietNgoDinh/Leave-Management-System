# Implementation Decisions — Addendum to the Master Spec

| | |
|---|---|
| Status | **APPROVED** (2026-09-30) — §1–§12. §13 (milestone 2, D-28 – D-44) is **PROPOSED** (2026-10-02); D-37 – D-44 were requested by the BA after the review of the master spec |
| Amends | [master-spec.md](master-spec.md) |
| Date | 2026-09-30, extended 2026-10-02 |

Where this addendum and the master spec disagree, **this addendum wins**. Each decision has an ID (D-nn), so you can approve or change any one of them on its own. §10 lists every place this document changes the master spec.

---

## 1. Platform and layout

**D-01 The runtime is Claude Code.**
- The **orchestrator is the main Claude Code session**, driven by `CLAUDE.md`. It can't be a subagent, because in Claude Code subagents can't start other subagents.
- Specialist agents go in `.claude/agents/<name>.md`.
- Skills go in `.claude/skills/<name>/SKILL.md`. There are two kinds:
  - **commands** that the user types, such as `/ba-status`, `/ba-next`, `/ba-spec`, `/ba-approve` and `/ba-changes`;
  - **method skills** that agents load, such as `write-acceptance-criteria` and `generate-sequence-diagram`.
- Hooks go in `.claude/settings.json`.
- The `ba-ai/skills/` and `ba-ai/agents/` folders from master §5 are dropped.

**D-02 Repository layout.**

```text
<ba-workspace>/              ← its own git repo; Claude Code is started here
├── CLAUDE.md                ← orchestrator rules
├── .claude/
│   ├── settings.json        ← hooks, permissions, additionalDirectories
│   ├── agents/
│   └── skills/
├── tools/                   ← `ba` CLI + hook scripts
├── docs/                    ← master spec + this addendum
└── ba-ai/                   ← all workflow artifacts (master §5 tree)
```

Product repos stay separate and are never merged. They are listed in `ba-ai/workflow/repositories.yaml` and made visible to Claude Code through `permissions.additionalDirectories` in `.claude/settings.json`. A `.code-workspace` file does the same for VS Code.

**D-03 Tooling is Python 3.9 plus PyYAML, in a project-local virtual environment.**
- This machine has Python 3.9.6, no Node and no YAML library.
- A `tools/ba` wrapper creates `.venv` from `requirements.txt` on first run.
- All code stays compatible with Python 3.9.
- There are no other dependencies. Validation is hand-written rather than using `jsonschema`.

**D-04 Bookkeeping goes in a `ba` CLI, not in prompts.** Anything that must be exactly right every time is a script:
- IDs;
- state;
- hashes;
- gate checks;
- the knowledge graph;
- validation;
- context packages.

The LLM does the analysis and the writing. The CLI does the bookkeeping.

| Command | What it does |
|---|---|
| `ba status` | Summarises runs, backlog progress, open gates and stale artifacts |
| `ba next-id <PREFIX>` | Allocates the next ID. Uses a file lock, so it's safe for parallel agents |
| `ba find <text>` | Searches existing items by name (Rule 4: reuse before creating) |
| `ba validate [path…]` | Checks artifacts against their schemas (D-19) |
| `ba context <UC-ID>` | Builds the context package for one use case (master §35) |
| `ba gate request <GATE> <SUBJECT>` | Opens a gate: validates, hashes the artifacts, records the request |
| `ba gate status [SUBJECT]` | Shows each gate as WAITING, APPROVED, CHANGES_REQUESTED or INVALIDATED |
| `ba sync` | Recomputes statuses from gates and hashes, updates frontmatter, backlog and state, and rebuilds the graph |
| `ba graph build` | Rebuilds `knowledge/ba-graph.json` from the artifacts |
| `ba state set …` | Moves a run's position (step, status, next step) |

---

## 2. State ownership

**D-05 Each shared file has one owner.**

| File | Holds | Written by |
|---|---|---|
| `workflow/state.json` | Workflow runs and their position | `ba` CLI only |
| `planning/backlog.yaml` | Progress per epic and use case | Status fields: `ba` CLI only. Descriptive fields such as name and priority: a human may edit them |
| `knowledge/id-registry.json` | ID counters | `ba next-id` only |
| `knowledge/ba-graph.json` | The graph | `ba graph build` only |
| `reviews/requests/` | Gate requests | `ba gate request` |
| `reviews/decisions/` | Human decisions | The hook only (D-10) |

- Agents write only the artifact files for the use case they're working on.
- Parallel subagents never edit shared files. They return their results, and the orchestrator runs `ba sync`.

**D-06 `state.json` holds several runs.** This allows a change request to start while a feature is still in progress.

```json
{
  "schema_version": 1,
  "active_run": "RUN-001",
  "runs": [{
    "run_id": "RUN-001",
    "workflow_type": "MODE_B",
    "status": "WAITING_FOR_HUMAN",
    "current_phase": "SPECIFICATION",
    "current_step": "GATE-03",
    "scope": { "epic": "EPIC-001", "use_cases": ["UC-001", "UC-002"] },
    "last_completed_step": "5.2",
    "next_step": "5.3",
    "blocked_reason": null,
    "origin_cr": null,
    "created_at": "…",
    "updated_at": "…"
  }],
  "coding_authorization": null,
  "updated_at": "…"
}
```

- Each use case's own position is stored in its backlog item as `current_step`. For example, UC-001 can be at GATE-04 while UC-002 is at step 5.6.
- Two fields from master §4 are no longer stored. `ba status` derives them instead:
  - `pending_approval` comes from open gate requests;
  - `artifacts_created` comes from the graph.

---

## 3. Statuses

**D-07 Each level has exactly one set of statuses, all written in UPPER_SNAKE_CASE.**

| Level | Field | Allowed values |
|---|---|---|
| Run | `status` | NOT_STARTED, IN_PROGRESS, WAITING_FOR_HUMAN, CHANGES_REQUESTED, BLOCKED, FAILED, COMPLETED |
| Backlog item | `status` | BACKLOG, READY, IN_PROGRESS, BLOCKED, DONE |
| Backlog stage | `ui_status`, `spec_status`, `technical_review_status`, `coding_status`, `testing_status`, `documentation_status` | NOT_STARTED, IN_PROGRESS, WAITING_FOR_REVIEW, CHANGES_REQUESTED, APPROVED, DONE, BLOCKED, STALE |
| Artifact | frontmatter `status` | DRAFT, WAITING_FOR_REVIEW, CHANGES_REQUESTED, APPROVED, STALE, SUPERSEDED |
| Gate | derived by `ba` | WAITING, APPROVED, CHANGES_REQUESTED, BLOCKED, INVALIDATED |

Three changes to the master spec follow from this:
- `DRAFT_FROM_CODE` (master §7) becomes `status: DRAFT` plus `origin: CODE`.
- `WAITING_FOR_QA` (master §24) becomes `coding_status: DONE` with `testing_status: NOT_STARTED`.
- `APPROVED` is removed from the run statuses, because approval belongs to gates.

---

## 4. Gates and approvals

**D-08 The gate list.** The gate IDs from master §37 are kept unchanged, following Rule 3 (stable IDs). Two gates are added.

| Gate | Opened after | Subject | Reviewer |
|---|---|---|---|
| GATE-01 CURRENT_STATE_REVIEW | Reverse engineering | Run | BA, plus SA for architecture |
| GATE-02 OVERVIEW_APPROVAL | Overview analysis | Run | BA |
| GATE-03 UI_MARKDOWN_REVIEW | Step 5.2 | Use case | BA |
| GATE-04 HTML_PROTOTYPE_REVIEW | Step 5.3 | Use case | BA or stakeholder |
| GATE-05 BA_SPEC_APPROVAL | **Step 5.8** (the master spec never places it) | Use case | BA |
| GATE-06 TECHNICAL_APPROVAL | GATE-05 | Use case | SA or developer |
| GATE-07 CRITICAL_FLOW_TEST | QA, only when required (D-23) | Use case | BA or QA |
| GATE-08 USER_GUIDE_REVIEW | User guide | Feature | BA |
| **GATE-09 TECH_BASELINE_APPROVAL** | Technical architecture baseline | Run | SA or tech lead |
| **GATE-10 CODE_REVIEW** | Coding: a pull request review in the product repo | Use case | Developer |

**D-09 A gate request freezes what is being reviewed.** `ba gate request GATE-03 UC-001` does the following:
1. Runs `ba validate` on the gate's artifacts, and refuses to continue if there are errors.
2. Takes a **content hash** of each artifact. The frontmatter fields `status`, `review` and `updated_at` are left out of the hash, so updating an artifact's status doesn't change it.
3. Writes `reviews/requests/UC-001/GATE-03.json`.
4. Sets the use case to WAITING_FOR_REVIEW and the run to WAITING_FOR_HUMAN.

The orchestrator then prints a review summary, including any open questions for that use case, and stops.

**D-10 Only a human can record a decision.**
- You type `/ba-approve UC-001 GATE-03 [comment]` or `/ba-changes UC-001 GATE-03 <comments>`.
- A `UserPromptSubmit` hook runs on the text you typed, before Claude sees it. It writes `reviews/decisions/UC-001/GATE-03-<timestamp>.json`, containing:
  - the decision;
  - the reviewer's name (`git config user.name`);
  - the time;
  - your comments;
  - the hashes of the artifacts being approved.
- A `PreToolUse` hook stops Claude from writing anything under `reviews/decisions/`. This covers Write, Edit, and Bash commands that mention that path.
- Both skills set `disable-model-invocation: true`, so Claude can't start them on its own.
- **To verify during the build:** that `UserPromptSubmit` reliably receives slash-command text. If it doesn't, the fallback is that you run `tools/ba decide …` in your own terminal.

This protects against the AI approving something by mistake. It isn't designed to stop a human who deliberately bypasses it.

**D-11 An approval is tied to the exact content that was approved.**
- A gate counts as APPROVED only when:
  - the latest decision is an approval; and
  - every artifact's current hash matches the hash recorded with that decision.
- Any edit after approval makes the gate INVALIDATED and the artifact STALE, and it needs approving again.
- This also gives change requests the "Technical review if required" rule from master §3 for free. If a change touches the API design, GATE-06 is invalidated automatically. If it doesn't, GATE-06 stays valid.

**D-12 Staleness passes downstream.** Each document lists the files it was built from, with their hashes:

```yaml
built_from:
  - path: ui/markdown/UC-001.md
    hash: 3f9a…
```

`ba sync` marks a document STALE when any hash in its `built_from` list no longer matches. The review feedback loop (master §38) regenerates only the STALE documents.

**D-13 A hook blocks coding before approval** (built with the Coding Engine, not in milestone 1).
- A `PreToolUse` hook blocks Write and Edit calls to files outside `<ba-workspace>`, meaning the product repos.
- Such writes are allowed only when `state.json.coding_authorization` names a use case whose GATE-05, GATE-06 and GATE-09 are currently APPROVED.
- `ba` sets that authorization only after checking all three gates.
- A hook can't catch every possible Bash command, so this is best-effort. GATE-10 code review is the backstop.

---

## 5. IDs

**D-14 ID format and allocation.**
- IDs look like `PREFIX-NNN`: three digits, growing to four when needed.
- The tools accept `UC-7` or `UC-07` and normalise them to `UC-007`.

| Node | Format | Example |
|---|---|---|
| Requirement | REQ-NNN | REQ-001 |
| Epic | EPIC-NNN | EPIC-001 |
| BusinessProcess | BP-NNN | BP-002 |
| ProcessStep | `<BP>-S<NN>` | BP-002-S03 |
| Actor | ACT-NNN | ACT-001 |
| UseCase | UC-NNN | UC-007 |
| Screen | SCR-NNN | SCR-014 |
| BusinessRule | BR-NNN | BR-003 |
| Entity | ENT-NNN (the entity's name goes in a `name` field, not in the ID) | ENT-005 |
| API | API-NNN | API-034 |
| Service / Application / Integration / Repository | SVC / APP / INT / REPO-NNN | SVC-002 |
| AcceptanceCriterion | `<UC>-AC-<NN>` | UC-007-AC-01 |
| Validation rule | `<UC>-VR-<NN>` | UC-007-VR-02 |
| Alternate / error flow | `<UC>-AF-<NN>`, `<UC>-EF-<NN>` | UC-007-EF-01 |
| TestCase | TC-NNN | TC-041 |
| Open question / assumption | Q-NNN / ASM-NNN | Q-012 |
| ChangeRequest | CR-NNN | CR-003 |
| Code reference | `CODE:<repo>/<path>` | CODE:backend-api/src/assets/assign.ts |

- Scoped IDs (AC, VR, AF, EF and process steps) are unique because they include their parent's ID. They use two digits.
- New global IDs come only from `ba next-id`, and `ba find` must be run first.
- IDs are never reused or renumbered, even after the item is deleted.

**D-15 The UserStory node is dropped.** The compiled use-case specification (master §21) *is* the user story. Acceptance criteria link directly with `AcceptanceCriterion VALIDATES UseCase`. A Jira-style story export can be added later.

**D-16 AS-IS and TO-BE.**
- A concept has one ID in both baselines.
- Every artifact and catalog item declares `baseline: AS_IS` or `baseline: TO_BE`.
- Each graph node lists its artifacts separately for each baseline.
- Anything under `current-state/` is always AS_IS.

---

## 6. Artifacts, schemas and validation

**D-17 Artifacts come in two shapes.**
- **Catalogs** hold many items in one file and are written in YAML. Examples:
  - `overview/use-cases.yaml`
  - `overview/business-rules.yaml`
  - `overview/business-processes.yaml`
  - `overview/actors.yaml`
  - `overview/data-model/entities.yaml`
  - `overview/integrations.yaml`
  - `technical/api/api-catalog.yaml`
  - `ui/screen-catalog.yaml`
  - the matching AS-IS catalogs under `current-state/`

  These replace the master spec's `use-cases.md`, `business-rules.md` and `integrations.md`.
- **Documents** have one subject per file and are written in Markdown with YAML frontmatter. Examples: the product overview, UI markdown, sequence, API design, use-case specification, test cases, impact analyses and user guides.

**D-18 Document frontmatter.** This replaces master §36. The pair (`id`, `artifact_type`) is unique across the workspace.

```yaml
---
id: UC-007
artifact_type: use-case-specification  # ui-markdown | ui-prototype | sequence | api-design | …
title: Assign Multiple Assets
status: DRAFT
version: 1                 # bumped by `ba gate request` when the content has changed
baseline: TO_BE
origin: AI                 # AI | HUMAN | CODE | FIXTURE
built_from:
  - { path: technical/api/UC-007.md, hash: … }
relations:                 # each key maps to a graph edge type
  business_process: [BP-002]
  business_rules: [BR-003, BR-007]
  entities_read: [ENT-004]
  entities_written: [ENT-005]
  screens: [SCR-014]
  apis: [API-034]
open_questions: [Q-012]
review:                    # written by `ba sync`; agents never edit this
  GATE-05: WAITING
updated_at: …
---
```

**D-19 What `ba validate` checks.** Any error blocks a gate request.
- Required frontmatter fields and allowed values.
- ID formats, and no duplicate IDs.
- Every ID that's referenced exists in a catalog or the ID registry.
- The required section headings for each document type. For example, a use-case specification must have all 20 sections from master §21.
- Every `built_from` hash still matches. A mismatch is a warning, and the document becomes STALE.

Semantic quality, such as whether acceptance criteria are testable or whether a decision was invented, is covered by a checklist in each method skill. The agent checks its own work against it, and the human gate is the final check.

**D-20 Unknowns are recorded, never guessed.**
- Open questions go in `requirements/clarification-log/open-questions.yaml` with IDs `Q-NNN`.
- Assumptions go in `requirements/assumptions/assumptions.yaml` with IDs `ASM-NNN`.
- The artifact they affect references them by ID.

---

## 7. Knowledge graph

**D-21 The graph is generated and never edited by hand.** `ba graph build` reads the catalogs and the document frontmatter, and writes `knowledge/ba-graph.json`:

```json
{
  "schema_version": 1,
  "generated_at": "…",
  "nodes": [{ "id": "UC-007", "type": "UseCase", "name": "Assign Multiple Assets",
              "status": "APPROVED",
              "artifacts": { "TO_BE": ["specifications/use-cases/UC-007.md"] } }],
  "edges": [{ "from": "UC-007", "type": "USES_RULE", "to": "BR-003",
              "source": "specifications/use-cases/UC-007.md" }]
}
```

- **Node types:** the core types from master §31; the Epic, AcceptanceCriterion, TestCase and Repository extensions; and three new types: **Requirement**, **CodeRef** and **ChangeRequest**.
- **Added edges:**
  - `UseCase SATISFIES Requirement`
  - `CodeRef IMPLEMENTS UseCase`
  - `CodeRef LOCATED_IN Repository`
  - `ChangeRequest AFFECTS *`
  - `AcceptanceCriterion VALIDATES UseCase`

  Together these close the traceability chain in master §39, from requirement through to implementation.
- The impact query (`ba graph impact <ID>`) is built together with the Change Request engine.

---

## 8. Routes

**D-22 `workflow/workflow.yaml` is the only route definition.** `workflow.md` is the human-readable explanation of it.

- **Change:** the Technical Baseline now runs *before* the Spec Engine, because Step 5.5 (API design) needs its API conventions.
- The map in master §43 gains GATE-09 and GATE-10.

```text
Spec Engine (per use case) =
  5.1 context → 5.2 UI markdown → GATE-03 → 5.3 prototype → GATE-04
  → 5.4 sequence → 5.5 API → 5.6 validation → 5.7 AC → 5.8 compile → GATE-05

MODE_A (existing product)
  Bootstrap → Reverse Engineering → GATE-01 → Technical Baseline (inferred from code) → GATE-09
  → Elicitation → Overview → GATE-02 → Planning → [Information Architecture if needed]
  → Spec Engine → GATE-06 → Coding → GATE-10 → QA → [GATE-07] → User Guide → GATE-08

MODE_B (new product, or a change too large for a CR)
  Bootstrap → Elicitation → Overview → GATE-02 → Technical Baseline (designed) → GATE-09
  → Planning → [Information Architecture] → Spec Engine → GATE-06 → Coding → GATE-10
  → QA → [GATE-07] → User Guide → GATE-08

MODE_C (small change request)
  CR intake → graph query → impact analysis → size classification
    LARGE → start a new MODE_B run with origin_cr set
    SMALL → update affected specs → re-approval of GATE-05, and GATE-06 if invalidated (D-11)
          → Coding → GATE-10 → QA → [GATE-07] → documentation update → [GATE-08]
```

**D-23 GATE-07 depends on risk.**
- Each use case has:
  - `risk_level`: LOW, MEDIUM, HIGH or CRITICAL;
  - `risk_flags`: any of FINANCIAL, IRREVERSIBLE, SECURITY, COMPLIANCE, PERSONAL_DATA.
- The AI proposes these during overview analysis, and the BA confirms them at GATE-02.
- GATE-07 is required when the risk level is HIGH or CRITICAL, or when any flag is set.

---

## 9. Later phases (decided now, built later)

**D-24 Reverse engineering.**
- One subagent works on each repo, then a merge step builds the chains that cross repos.
- Every item it produces carries:
  - `origin: CODE`;
  - `evidence: [{repo, path, line}]`;
  - `confidence`: HIGH, MEDIUM or LOW.

**D-25 Coding.**
- Each use case gets its own branch in each affected repo: `ba/UC-007-<slug>`.
- Commit messages reference the use case and acceptance criterion IDs.
- The AI never pushes, merges or opens pull requests unless the user asks. GATE-10 is a human review of the pull request.
- Changed files are recorded as CodeRef nodes, and D-13 enforces the approval precondition.

**D-26 QA.**
- The fix loop tries at most 3 times per defect. After that the defect is marked UNRESOLVED and passed to a human.
- UI tests and user-guide screenshots use Playwright. The install method will be chosen when QA is built.

**D-27 Prototypes.**
- Plain HTML, CSS and JavaScript with no build step, so they open straight from disk.
- Each use case gets `ui/prototypes/<UC-ID>/index.html`, and shared assets go in `ui/prototypes/_shared/`.
- Styling comes from `ui/design-system.md`. For existing products it's inferred from the code; new products get a minimal default.

---

## 10. Changes to the master spec

| Master spec | Changed to | Decision |
|---|---|---|
| §5 `ba-ai/skills/`, `ba-ai/agents/` | `.claude/skills/`, `.claude/agents/` | D-01 |
| §32 orchestrator as an agent | Main session + `CLAUDE.md` | D-01 |
| §4 single run; stored `pending_approval` and `artifacts_created` | Several runs; those two fields derived | D-06 |
| §4 run status `APPROVED` | Removed | D-07 |
| §24 `WAITING_FOR_QA`; §7 `DRAFT_FROM_CODE` | Mapped onto the single status sets | D-07 |
| §5 `reviews/{ba,stakeholder,technical}` | `reviews/{requests,decisions}` | D-09, D-10 |
| §37 eight gates; GATE-05 placement not stated | Two gates added (09, 10); GATE-05 placed after Step 5.8 | D-08 |
| §36 `ENT-ASSET`; two-digit IDs; `AC-01` | `ENT-005`; three digits; `UC-007-AC-01` | D-14 |
| §31 UserStory node | Dropped | D-15 |
| §36 `source` / `dependencies` / free-text `version` | `relations`, `built_from`, integer `version` | D-12, D-18 |
| §8–9 `use-cases.md`, `business-rules.md`, `integrations.md`, `open-questions.md`, `assumptions.md` | YAML catalogs | D-17, D-20 |
| §3 routes; §23 baseline placement | Unified routes, with the baseline before the Spec Engine | D-22 |
| §4 "status = WAITING_FOR_HUMAN" in step 2.5 | Derived from OPEN questions marked `blocking` | D-30 |
| §9 3.4 state model as its own artifact | The entity's `lifecycle` in the data model | D-31 |
| §12 information architecture "when required" | When an application is marked `information_architecture: REQUIRED` | D-32 |
| §3, §43 run-level GATE-06 … GATE-08 after the Spec Engine | Per-use-case steps in one engine | D-33 |
| §24 coding precondition | `tools/ba coding authorize`; hook pending | D-33, D-36 |
| §25 step 8.4 retry limit; D-26 Playwright install method | Defects file + routing by classification; Playwright from the frontend repo | D-34 |
| D-08 GATE-08 subject "Feature" | One guide per use case | D-35 |
| D-22 order Coding → GATE-10 → QA | Acceptance tests → Coding → QA and fix loop → GATE-10 → GATE-07 | D-37, D-38 |
| §25 tests generated after implementation | Acceptance tests written by the QA agent before coding | D-38 |
| D-25 a branch per use case in each repo | A git worktree per use case per repo, plus a shared repository-setup step | D-39 |
| §37 the human gates alone | An AI pre-review before each human gate (except GATE-07) | D-40 |
| §41 Rule 5 "retrieve only the information necessary" | The context package is a map; agents may read further and say what | D-41 |
| §8 2.5 / §41 Rule 1: unknowns only as logged questions | Blocking questions go to the BA live, in the session | D-42 |
| §21 the agent compiles all 20 sections | `tools/ba compile` assembles 13; the agent writes 7 narrative sections | D-43 |

---

## 11. Milestone 1

**Goal:** Use Case → Spec Engine → Human Review → code-ready specification (master §44). State, gates, IDs, validation and the graph work underneath.

**Project data.**
- The kit ships as an empty template: every catalog and the backlog are empty, and there is one MODE_B run (RUN-001).
- The Spec Engine needs a project to run on. Because milestone 1 has no overview or baseline engine, these are written by hand:
  - a product overview with its catalogs (requirements, actors, applications, business processes, business rules, entities, integrations, use cases);
  - a technical baseline (architecture, services, coding rules, security rules);
  - a design system;
  - a backlog with at least one epic and its use cases.
- **GATE-02 and GATE-09 start open.** You approve them yourself, as the first real test of the gate mechanism.

**Built in milestone 1**
- The `ba-ai/` tree, `workflow.yaml` and `workflow.md`. All routes are declared, but only the Spec Engine steps can run.
- The `tools/ba` CLI (D-04), the virtual environment setup, and the gate hooks (D-10).
- Schemas for the milestone 1 artifact types.
- Commands: `/ba-status`, `/ba-next` (resume), `/ba-spec [UC|EPIC]`, `/ba-approve`, `/ba-changes`.
- Agents:
  - `ui-agent` for Steps 5.2–5.3;
  - `technical-analysis-agent` for Steps 5.4–5.6;
  - `spec-agent` for Steps 5.7–5.8.
- Method skills:
  - `design-screen-markdown`
  - `build-html-prototype`
  - `generate-sequence-diagram`
  - `design-api`
  - `analyze-validation`
  - `write-acceptance-criteria`
  - `compile-use-case-spec`
- `CLAUDE.md` with the orchestrator rules. Step 5.1 is `ba context` plus a check by the orchestrator, not a separate agent.

**Not in milestone 1:**
- the reverse engineering, elicitation, overview and planning engines;
- technical review (GATE-06);
- coding and the D-13 hook;
- QA and Playwright;
- the user guide;
- change requests and impact analysis.

**Acceptance tests.** Tests 1, 2, 7, 8 and 9 are run by Claude. Tests 3–6 need you to type approvals, and Claude will prompt you at each gate.

1. With the overview and technical baseline in place and nothing approved yet, `/ba-status` shows RUN-001 waiting on GATE-02 and GATE-09.
2. When Claude tries to write to `reviews/decisions/`, the hook blocks it.
3. After you approve GATE-02 and GATE-09, `/ba-spec` picks the highest-priority READY use case, writes its UI markdown, and stops at GATE-03.
4. After `/ba-changes` with a comment, only the UI markdown is regenerated, and a new GATE-03 request is opened.
5. You approve GATE-03. The prototype is built and it stops at GATE-04. You approve that, and it produces the sequence, API design, validation, acceptance criteria and compiled spec, then stops at GATE-05. `ba validate` passes on everything.
6. After you close the session, `/ba-next` in a new session resumes at exactly the same step.
7. On a scratch copy, editing an approved business rule makes the spec STALE and GATE-05 INVALIDATED.
8. `/ba-spec EPIC-001` runs the remaining use cases in parallel. State, backlog and ID registry stay consistent, with no duplicate IDs.
9. The graph contains edges from use cases to business rules, entities, screens, APIs and acceptance criteria. A reverse lookup from an API reaches its use case and business process.

---

## 12. Open items (to decide later)

- Whether classifying a change request as SMALL or LARGE needs its own gate (a possible GATE-11). To decide when building the Change Request engine.
- Exporting the backlog and stories to Jira or Azure DevOps.
- At what size to move from `ba-graph.json` to a graph database.
- Splitting the reusable kit from each product's instance, for example a `ba init` command that sets up a fresh `ba-ai/` in a product workspace.

---

## 13. Milestone 2 — MODE_B end to end (PROPOSED, 2026-10-02)

**Goal:** a new product runs the whole MODE_B route (D-22), from stakeholder material to an approved user guide. Every run-level phase and every per-use-case phase after GATE-05 now has an engine. MODE_A reverse engineering (D-24) and the MODE_C change-request engine are still to come.

Three choices below were made by the BA on 2026-10-02:
- no planning gate (D-32);
- Playwright from the product toolchain (D-34);
- one user guide per use case (D-35).

**D-28 Run-level engines are declared in `workflow.yaml`.**
- Each `run_steps` entry names:
  - its agent and method skills;
  - the inputs it requires;
  - the documents it writes, with their `built_from` inputs;
  - the catalogs it must fill.
- An input ending in `?` is optional: it may still be empty. `tools/ba stamp` records an empty optional input with `hash: null`, and the document turns STALE once the input appears. That is how new meeting notes trigger consolidation (master §8 step 2.6).
- The steps and their agents:

| Step | Agent | Writes |
|---|---|---|
| ELICITATION (Phase 2) | elicitation-agent | elicitation summary, requirements, open questions, assumptions |
| OVERVIEW (Phase 3) | overview-analysis-agent | product overview, actors, applications, processes, rules, entities, integrations, use cases |
| TECH_BASELINE (Phase 6A, designed) | technical-baseline-agent | architecture, coding rules, security rules, design system, services, repositories |
| PLANNING (Phase 4) | planning-agent | backlog, via `tools/ba backlog plan` |
| INFORMATION_ARCHITECTURE (Phase 4A) | planning-agent | one IA document per application, planned screens |

**D-29 When a run-level step is complete.**
- **With a gate after it:** the step is complete once that gate (GATE-02 or GATE-09) is APPROVED. An approval freezes what came before it. Later changes go through the overview-change procedure (`--force-gated`, which re-opens the gate). They never come from silently regenerating upstream steps.
- **Without a gate after it** (planning, IA): the step is complete when its outputs exist, are current, are valid and are stamped. For planning, that also means every use case in the catalog is in the backlog.
- **The next action** is derived like a use case's: GENERATE (missing), REGENERATE (stale), FIX (invalid or unstamped).
- Projects built by hand in milestone 1 keep their position: their GATE-02 and GATE-09 approvals mark the upstream steps complete.

**D-30 The stakeholder wait (master §8 step 2.5) is derived.**
- An open question with `blocking: true` must be answered before the overview can be written. While one is OPEN, the run is WAITING_FOR_HUMAN with the action WAIT_FOR_STAKEHOLDERS.
- The BA holds the conversation and puts the notes in `requirements/meetings/`. This makes the elicitation summary STALE, and the elicitation agent consolidates them (2.6).
- A question becomes ANSWERED only with an `answer_source` that points at stakeholder material. Neither the AI nor the orchestrator answers questions. When the BA answers in chat, the orchestrator saves their words verbatim as a meeting note.

**D-31 The state model lives on the entity.** An entity's `lifecycle` holds three lists:
- `states`;
- `transitions`, written `FROM -> TO: event` (or as a mapping);
- `invalid_transitions`.

`tools/ba validate` checks that every transition uses listed states and names an event. GATE-02 reviews the lifecycle with the data model. This keeps GATE-02's artifact list unchanged, so existing approvals stay valid.

**D-32 Planning and information architecture.**
- **The backlog is written through `tools/ba backlog plan --file <plan>`.** A plan lists epics (new ones get IDs from the tool) with their use cases, priorities, dependencies and proposed status (BACKLOG, READY or BLOCKED).
- **The tool rejects** a use case planned twice, an unknown use case, a dependency cycle, and dropping a use case whose work has started.
- **A re-plan never undoes progress:** IN_PROGRESS and DONE stay, and so do derived fields.
- **Phase 4A runs once per application with `information_architecture: REQUIRED`.** The overview analysis proposes that flag (a new application, or a major navigation change, master §12) and the BA confirms it at GATE-02. The IA registers the planned screens in the screen catalog, so step 5.2 reuses them.
- **No new gate (BA decision).** The backlog and the IA are reviewed through each use case's GATE-03. The BA can edit priority, status and dependencies in `backlog.yaml` at any time.

**D-33 Delivery steps run per use case, in one engine.**
- The per-use-case engine continues after GATE-05, in this order (D-37, D-38):
  - 6 GATE-06;
  - 8.1 acceptance tests, written before any code;
  - 7 implementation (7.0 repository setup first, when a repository doesn't exist yet);
  - 8.2 test results, with the fix loop (8.3–8.4);
  - GATE-10 code review, on the tested code;
  - GATE-07 when D-23 requires it;
  - 9 user guide, then GATE-08.
- In the routes, the run-level GATE-06 … GATE-08 entries become one `DELIVERY` engine entry. The run is COMPLETED when every use case in scope has GATE-08 approved.
- **GATE-06 covers only `technical/sequence/<UC>.md` and `technical/api/<UC>.md`.** A change that leaves them untouched keeps GATE-06 valid (D-11). An SA change makes the spec STALE, so GATE-05 is approved again before GATE-06 is re-requested.
- **Coding precondition (master §24, D-13).**
  - `tools/ba coding authorize <UC>` checks GATE-05 and GATE-06 for the use case and GATE-09 for the run. Only then does it add the use case to `state.json.coding_authorization`.
  - Every action that writes in a product repository (7.0, 8.1, 7, 8.2, 8.4, 9) carries it as `pre_command`.
  - `tools/ba sync` drops an authorization when a gate no longer holds, or when the use case is delivered (GATE-08).
- **The implementation summary** (`technical/implementation/<UC>.md`) records the repositories, the branch `ba/<UC>-<slug>`, the commits and `code_refs` (`CODE:<repo>/<path>`). The graph turns these into `CodeRef IMPLEMENTS UseCase` and `CodeRef LOCATED_IN Repository`.
- **Backlog stage statuses.**
  - `technical_review_status` follows GATE-06.
  - `coding_status` becomes DONE at GATE-10, which now comes after QA (D-37). D-07's "WAITING_FOR_QA" mapping no longer applies.
  - `testing_status` becomes DONE only after QA passed and GATE-07, when required, is approved.
  - `documentation_status` becomes DONE at GATE-08, and so does the item's `status`.

**D-34 QA loop, defects and test tooling.**
- **Test cases** (`qa/test-cases/<UC>.md`):
  - IDs come from `tools/ba next-id TC`;
  - each one says what it verifies (`<UC>-AC-nn`), its category and its steps and expected result;
  - every acceptance criterion must be verified (validated);
  - the graph adds `TestCase VERIFIES AcceptanceCriterion`.
- **Test results** (`qa/test-results/<UC>.md`) carry `outcome` (PASSED, FAILED or BLOCKED) and `executed_at`.
- **Defects** are in `qa/defects/<UC>.md`:
  - each has an ID `<UC>-DEF-nn` with an expected-vs-actual section;
  - the frontmatter list holds its classification (master §25 step 8.3), its status (OPEN, FIXED or UNRESOLVED) and its `fix_attempts`.
- **Routing by classification:**
  - TEST_ISSUE → the QA agent fixes the tests (FIX_TESTS).
  - CODE_DEFECT under 3 attempts → the coding agent fixes it (FIX_DEFECT, step 8.4).
  - SPECIFICATION_GAP, ENVIRONMENT_ISSUE, UNRESOLVED, or a CODE_DEFECT after 3 attempts → NEEDS_HUMAN. The run waits, and a human decides.
- **After a human fix**, `tools/ba qa retest <UC>` asks for a new run.
- **The fix loop runs before code review** (D-37): fix → retest → compare with no human in between, at most 3 attempts per defect. GATE-10 then reviews the final, tested code once.
- **Playwright is installed in the product's frontend repository** with its own package manager (BA decision; this settles the open point in D-26). The technical baseline's *Testing Conventions* names the commands. The kit itself stays Python-only (D-03).

**D-35 One user guide per use case** (BA decision; this settles D-08's "Feature").
- The guide is `user-guide/<UC>/guide.md`, with its screenshots in `user-guide/<UC>/screenshots/`.
- GATE-08 hashes the whole folder, so a changed screenshot needs re-approval.
- Screenshots come from the implemented application, never the prototype. `tools/ba validate` checks that every referenced image exists.

**D-36 Protected-file changes wait for maintenance mode.** Two changes need `BA_MAINTENANCE=1`:
- wiring `coding.write_allowed()` into the PreToolUse hook;
- listing the product repositories in `permissions.additionalDirectories`.

[tools/patches/d13-coding-hook.md](../tools/patches/d13-coding-hook.md) holds both. Until they are applied, the orchestrator enforces the coding precondition (CLAUDE.md, hard rule 9).

### Review changes (2026-10-02, requested by the BA)

The BA asked for a review of the master spec's approach, which was drafted by another AI model, against how Claude works best. These decisions came out of it.

**D-37 Automated QA runs before code review.**
- Claude works best by iterating until the tests pass and then handing over for review.
- With D-22's order (Coding → GATE-10 → QA), every automated fix invalidated GATE-10, so the developer re-reviewed after each fix.
- Now:
  - the fix loop (D-34) runs to green first;
  - GATE-10 reviews the final code once, and covers the implementation summary and the test results;
  - GATE-07 (human critical-flow test) follows, on reviewed code.
- A GATE-10 change request goes to the coding agent, and the changed code is tested again before GATE-10 is re-requested.

**D-38 Acceptance tests are written first, by the QA agent.**
- Step 8.1 runs right after GATE-06, before any code. The QA agent turns the approved acceptance criteria, rules, validations and API design into executable tests:
  - API tests against the designed contract;
  - Playwright tests that find elements by role and label from the approved UI.
- They are committed in the use case's worktree and listed in `test_files`, with `tests_commit`.
- The coding agent makes them pass and may not edit them. QA verifies at 8.2 that they are unchanged.
- The result is a precise, executable definition of done, while QA stays independent of the implementation.

**D-39 One git worktree per use case, and a shared repository setup.**
- D-25's branch per use case broke parallelism: two coding agents in one checkout switch branches under each other.
- Each use case now works in `<repo>-worktrees/<UC>/` (branch `ba/<UC>-<slug>`). QA and the user guide use the same worktree, and servers start on a free port.
- Before the first step that needs product repositories, a shared action SETUP_REPOSITORIES (step 7.0) creates the repositories the approved baseline lists and marks them ACTIVE. The orchestrator runs it once.
- Coding authorization and the D-13 hook govern the repositories and their worktree folders.
- Worktrees are removed by the human after merging.

**D-40 AI pre-review before each human gate.**
- Before a gate (all except GATE-07, which is human testing) is requested, a `review-agent` with a fresh context checks the artifacts. Its criteria are their inputs, the producing method skills' checklists and the gate's review focus.
- It records PASS or FINDINGS with `tools/ba prereview record`. The record is hashed like a gate request and stored in `reviews/pre-review/`. It is never a gate decision.
- FINDINGS go to the artifact's owner, who fixes them or records why they stay (`tools/ba prereview resolve`).
- After at most 2 rounds the gate is requested anyway, and the remaining findings are shown to the human.
- `tools/ba gate request` refuses while the pre-review is due, unless the BA asks for `--skip-pre-review`.

**D-41 The context package is a map, not a fence** (Rule 5 reinterpreted).
- Rule 5 was written for small context windows. Agents start from the package, which keeps the missing-input check deterministic.
- They may read further, with `tools/ba find`, `graph show` and Grep, when the task needs it. The coding agent explores the codebase as much as the change needs.
- They name the extra files in their summary, so the package can be improved (Rule 8).

**D-42 Blocking questions go to the BA live.**
- An agent that can't do its step responsibly without a human answer returns `QUESTION FOR THE BA:` with options. Subagents can't ask the user themselves.
- The orchestrator asks the BA in the session and records the answer with its source "BA (<name>) in the session, <date>". For elicitation, the answer is saved verbatim as a meeting note.
- Non-blocking unknowns are still logged as open questions (Rule 1). Stakeholder decisions are never simulated: the BA says on whose behalf they answer.

**D-43 The compiled spec is assembled by the tool.**
- `tools/ba compile <UC>` builds the 20-section specification (master §21). It copies or derives 13 sections from their sources: actor, UI screens, AF, EF, rules, VR, entities, sequence, API summary, AC, assumptions, open questions, traceability.
- The spec agent writes only the 7 narrative sections. A recompile keeps them.
- `tools/ba validate` rejects a hand-edited generated section, and a narrative section left as a TODO.
- A model re-typing six documents invites paraphrase drift and costs tokens; the tool can't drift. A section that doesn't apply says "Not applicable."

**D-44 Notes on the master spec itself.**
- The master spec was drafted by another AI model. Its statements about what "the workshop" said ("the workshop explicitly describes…") are unverified: check them against the workshop's own notes before relying on them.
- Instructions in CLAUDE.md, the agents and the skills give the reason for each hard rule rather than bare absolutes. Claude follows instructions literally, and a reason lets it handle the edge cases a rule didn't foresee.
- Found while building: a product with no external integrations could never pass GATE-02, because the gate requires `overview/integrations.yaml` to exist. `tools/ba catalog init <catalog>` now creates an empty catalog, and the engine sends the producing step back when a gate artifact is missing.

**Built in milestone 2**
- `workflow.yaml` holds the run steps and the delivery steps, with GATE-06, 07, 08 and 10 implemented.
- `tools/ba` gains:
  - `context <STEP>` (a run-level context package);
  - `backlog plan`;
  - `coding authorize|revoke|status`;
  - `qa retest`;
  - optional inputs, staleness of run-level documents, the QA routing, and the new checks.
- `catalog add business-processes` numbers steps given without an ID (`<BP>-S01`, …).
- Agents: `elicitation-agent`, `overview-analysis-agent`, `technical-baseline-agent`, `planning-agent`, `coding-agent`, `qa-agent`, `documentation-agent`, `review-agent`.
- From the review changes: `tools/ba compile`, `tools/ba prereview brief|record|resolve|status`, `tools/ba catalog init`, worktree paths in the context package, the SETUP_REPOSITORIES action, and the skills `pre-review-gate` and `set-up-repositories`.
- Method skills:
  - `elicit-requirements`, `generate-clarification-questions`;
  - `write-product-overview`, `model-business-processes`, `extract-business-rules`, `build-data-model`, `define-use-cases`;
  - `design-technical-baseline`;
  - `plan-backlog`, `design-information-architecture`;
  - `implement-use-case`, `fix-defects`;
  - `generate-test-cases`, `execute-tests`;
  - `write-user-guide`;
  - `pre-review-gate`, `set-up-repositories`.
- Regression tests: `tools/tests/test_mode_b.py` walks a fixture product through every MODE_B step. Gate states are stubbed in memory, so no decision record is ever written.

**Acceptance tests (milestone 2).** Claude runs 1–4 and 8. Tests 5–7 need a product with stakeholder material and someone to type the approvals.
1. On a fresh template, `/ba-status` shows RUN-001 NOT_STARTED, waiting for material in `requirements/raw/`.
2. With material in `raw/` and a blocking question open, the run waits for stakeholders. Adding a meeting note in `meetings/` triggers consolidation.
3. A use case added after planning re-opens PLANNING. Raising a use case's risk to HIGH makes GATE-07 mandatory.
4. A CODE_DEFECT goes to the fix loop at most 3 times, then waits for a human. A TEST_ISSUE goes to the QA agent. Neither involves GATE-10, which comes only after QA passed. Each gate is preceded by an AI pre-review of at most 2 rounds.
5. From stakeholder material to GATE-02, GATE-09, a planned backlog and IA, then the Spec Engine (milestone-1 tests 3–5).
6. After GATE-05 and GATE-06, `tools/ba coding authorize` succeeds. The QA agent commits failing acceptance tests in `<repo>-worktrees/<UC>`, and the coding agent makes them pass in the same worktree without editing them or pushing. Two use cases coded in parallel don't interfere.
7. QA passes, then GATE-10, GATE-07 (if risky), the user guide, GATE-08 and `status: DONE`.
8. The milestone-1 Leave Management run keeps its exact position and every gate status after the upgrade.

