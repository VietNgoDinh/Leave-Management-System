# BA End-to-End AI Workflow — Claude Code kit

A stateful Business Analyst workflow for Claude Code. It runs from use case to code-ready specification, with human approval gates, stop/resume, a traceability graph and parallel agents.

- What it is and why: [docs/master-spec.md](docs/master-spec.md) + [docs/implementation-decisions.md](docs/implementation-decisions.md)
- How it runs: [ba-ai/workflow/workflow.md](ba-ai/workflow/workflow.md)
- Status: **milestone 1**, the BA Specification Engine (steps 5.1–5.8, gates GATE-02/03/04/05/09). The repository ships as an empty template: `ba-ai/` holds no project data yet.

## Start

1. Open this folder in VS Code and start Claude Code **in this folder**. Hooks and skills load at startup. The first `tools/ba` call creates `.venv` (needs Python 3.9+ and internet once).
2. Type `/ba-status`. On a fresh copy RUN-001 is blocked at the overview step, because there is no project data yet.
3. Add your project (see [Starting a project](#starting-a-project)).
4. Follow what `/ba-status` asks. Once the overview and baseline exist, that is:
   - `/ba-next` — Claude requests GATE-02 (overview) review.
   - Review the files it lists, then `/ba-approve RUN-001 GATE-02`.
   - The same for GATE-09 (technical baseline).
   - `/ba-spec` (top-priority use case) or `/ba-spec EPIC-001` (every ready use case, in parallel).
   - At each gate: review, then `/ba-approve <UC> <GATE>` or `/ba-changes <UC> <GATE> <what to change>`.

## Commands

| Command | Does |
|---|---|
| `/ba-status` | Where things stand, what waits for you |
| `/ba-next [UC\|EPIC]` | Resume from exactly where it stopped |
| `/ba-spec [UC\|EPIC]` | Run the Spec Engine |
| `/ba-approve <SUBJECT> <GATE> [comment]` | Approve a gate |
| `/ba-changes <SUBJECT> <GATE> <comments>` | Request changes |

Only you can approve. Your typed `/ba-approve` is recorded by a hook before Claude sees it, and Claude is blocked from writing decision records. If the hook ever fails, record the decision yourself in a terminal: `tools/ba decide approve <SUBJECT> <GATE> "comment"`.

## Layout

```text
CLAUDE.md            orchestrator rules (the main Claude session)
.claude/agents/      ui-agent, technical-analysis-agent, spec-agent
.claude/skills/      commands (/ba-*) and the BA method skills used by agents
.claude/settings.json  gate hooks + permissions
tools/ba             bookkeeping CLI (state, IDs, gates, validation, graph)
tools/schemas/       catalog and artifact schemas
ba-ai/               all workflow artifacts (your project data)
docs/                master spec + implementation decisions
```

## Starting a project

Milestone 1 has no elicitation, overview or baseline engine, so the Spec Engine's inputs are written by hand, or drafted with Claude from your raw material (put it in `ba-ai/requirements/raw/`). (A `ba init` scaffold is on the roadmap.)

| What | Files under `ba-ai/` | Reviewed at |
|---|---|---|
| Overview | `overview/product-overview.md`, and the catalogs `requirements/requirements.yaml`, `overview/actors.yaml`, `applications.yaml`, `business-processes.yaml`, `business-rules.yaml`, `data-model/entities.yaml`, `integrations.yaml`, `use-cases.yaml` | GATE-02 |
| Technical baseline | `technical/architecture/architecture.md` and `services.yaml`, `technical/coding-rules/frontend.md` and `backend.md`, `technical/security/security-rules.md`, `ui/design-system.md` | GATE-09 |
| Backlog | `planning/backlog.yaml` — epics, each with its use cases | — |

- Catalog items are added with `tools/ba catalog add <catalog> --data '{…}'`, which allocates the IDs. Required fields are in `tools/schemas/catalogs.yaml`.
- The Markdown documents need the frontmatter and headings listed in `tools/schemas/artifacts.yaml`. `tools/ba validate` reports what is missing.
- Set the project name in `ba-ai/workflow/state.json` (`project.name`). The template starts with one run, RUN-001, in MODE_B (new product).
- Put the product repositories next to this folder. List them in `ba-ai/workflow/repositories.yaml` and in `permissions.additionalDirectories` in `.claude/settings.json`.

## Maintaining the kit

Hook-protected files — `.claude/settings.json`, `tools/ba`, `tools/ba_cli/hooks.py`, `tools/ba_cli/gates.py` — can only be edited by Claude when you start it with `BA_MAINTENANCE=1 claude`. Everything else (skills, schemas, agents) can be improved normally (Rule 8).
