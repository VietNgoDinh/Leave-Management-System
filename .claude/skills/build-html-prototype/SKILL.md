---
name: build-html-prototype
description: BA Spec Engine step 5.3 — build a clickable, self-contained HTML prototype from the approved functional UI (ba-ai/ui/prototypes/<UC>/). Used by ui-agent; not for direct use.
user-invocable: false
---

# Step 5.3 — Interactive HTML Prototype

| | |
|---|---|
| Input | **Approved** `ba-ai/ui/markdown/<UC>.md` (GATE-03), `ba-ai/ui/design-system.md`, context package |
| Output | `ba-ai/ui/prototypes/<UC>/index.html` and `ba-ai/ui/prototypes/<UC>/README.md` |
| Consumers | BA/stakeholder review (GATE-04) → sequence analysis (5.4) |

The prototype validates requirements. It is not production code.

## Rules

- **Self-contained:** one `index.html` with inline CSS and JavaScript. No CDNs, no fetch, no build step; it must work opened straight from disk. Extra files (images) go in the same folder.
- **Faithful:** the markdown is the specification. Every screen, field, action, state and message in it appears here with the same labels and text. Add nothing the markdown doesn't define; if you find a gap, note it in README → Limitations and raise an open question instead of designing around it.
- **Navigable:** hash routes per screen (`#/scr-001`), wrapper `<section data-screen="SCR-001">`. Navigation follows the markdown's Navigation section.
- **Interactive enough to validate behaviour:**
  - client-side validation with the exact messages from the markdown, triggered on blur and on submit, plus the error summary pattern from the design system;
  - dialogs, confirmation steps and success toasts as described;
  - realistic, clearly fictional in-memory sample data.
- **Prototype controls panel** (small collapsible panel, bottom-right, labelled "Prototype controls"): force each state the markdown lists (empty, loading, server errors such as a business-rule 409 or a 503 dependency outage) and reset the data. This is how reviewers see non-happy paths.
- A fixed banner: "Prototype — <UC> <name> — not production code".
- Put `data-rule="BR-xxx"` on elements that show a rule-driven message, so reviewers can trace behaviour to rules.
- Basic accessibility: every input has a `<label for>`; actions are `<button>`s.
- Styling uses the design system's colours, components and layout.

## README template

````markdown
---
id: <UC>
artifact_type: ui-prototype
title: <use case name> — Interactive Prototype
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
relations:
  screens: [<SCR>, ...]
  business_rules: [<BR>, ...]
open_questions: []
updated_at: ""
---
# <UC> — <use case name>: Interactive Prototype

## How to Open
Open `ba-ai/ui/prototypes/<UC>/index.html` in a browser (double-click; no server needed).

## Screens Covered
| Screen | Prototype route | Notes |
|---|---|---|

## Interactions
The reviewer's script — one numbered path per flow:
1. Main flow: …
2. <alternate / error flow>: how to trigger it (for example "Prototype controls → Simulate 409") and what should happen.

## Limitations
What is simulated or not represented (for example "no real lookup in the external system; sample records only").
````

## Finish

1. `tools/ba stamp ba-ai/ui/prototypes/<UC>/` (stamps README.md) and `tools/ba validate ba-ai/ui/prototypes/<UC>/`.
2. Check the page parses: `python3 -c "import html.parser,sys; html.parser.HTMLParser().feed(open(sys.argv[1]).read())" ba-ai/ui/prototypes/<UC>/index.html`.
