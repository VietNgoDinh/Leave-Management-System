---
id: CODING-FRONTEND
artifact_type: coding-rules
title: Frontend Coding Rules
status: APPROVED
version: 1
baseline: TO_BE
origin: AI
updated_at: 2026-09-30 09:12:44+00:00
review:
  GATE-09: APPROVED
---
# Frontend Coding Rules

React 18 and TypeScript, in the repository REPO-002. Visual rules are in the design system; these rules cover how the code is written.

## Conventions

Structure:

- Code is grouped by feature under `src/features/<feature>`. A feature holds its pages, components, API calls and tests.
- Code used by more than one feature moves to `src/shared`.
- One component per file, named in PascalCase. Hooks start with `use`. Files that hold no component are kebab-case.

TypeScript:

- `strict` mode is on. `any` is not allowed; use `unknown` and narrow it.
- API request and response types are generated from the backend's OpenAPI description, not written by hand.

Data:

- All server data goes through TanStack Query. Components do not call `fetch` directly.
- No global state library. State that belongs to the URL (filters, page, sort) lives in the URL, so a filtered list can be bookmarked and shared.
- After a successful change, invalidate the affected queries instead of patching the cache by hand.

Forms and validation:

- Forms use Ant Design `Form`. Client-side validation repeats the server rules for fast feedback, but the server stays the authority.
- Server field errors are mapped onto the fields by their `field` name; error messages come from the error `code`.
- A submit button is disabled while its request is running.

User interface:

- Use Ant Design components. A custom component is justified only when none fits.
- All user-visible text lives in one messages file per feature, even though the product is English only.
- Every page handles four states: loading, empty, error and content.
- Every page works at 360 px width and with the keyboard alone.
- Dates are shown in the user's locale format; the API always receives `YYYY-MM-DD`.

Access:

- Routes and actions a role cannot use are hidden, using the roles from the current-user endpoint. Hiding is for convenience only; the server enforces access.

Quality:

- ESLint and Prettier run in the build; warnings fail it.
- Each form and each table with filters has component tests for its validation and its states.
