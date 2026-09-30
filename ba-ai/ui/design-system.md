---
id: DESIGN-SYSTEM
artifact_type: design-system
title: Design System
status: APPROVED
version: 1
baseline: TO_BE
origin: AI
updated_at: 2026-09-30 09:12:44+00:00
review:
  GATE-09: APPROVED
---
# Design System

A minimal default for a new product, based on Ant Design 5, which the web application uses. Screen designs name these components and patterns; prototypes reproduce them in plain HTML and CSS with the values below.

## Principles

1. **The next action is obvious.** Each screen has one primary action. Reviewers land on the requests that need them.
2. **Status is always visible.** A leave request shows its status as a tag wherever it appears.
3. **Explain before blocking.** A rule that blocks submission says which rule and how to fix it. A request that exceeds the entitlement shows a warning and can still be submitted.
4. **Works on a phone.** Every screen is usable at 360 px width. Employees often request leave from a phone.
5. **Accessible.** WCAG 2.1 level AA: text contrast of at least 4.5:1, full keyboard operation, visible focus, labels on every field. Colour is never the only signal.
6. **Plain English.** Short labels, sentence case, no jargon. Dates are written out where space allows: 5 Jan 2026.

## Layout

Page frame:

- Top bar, 56 px high: product name on the left; user name, role and sign-out on the right.
- Side navigation, 220 px wide, listing the areas the user's roles allow. Below 992 px it collapses into a menu button in the top bar.
- Content area with a page header (title, optional description, primary action on the right) and the page body. Maximum content width 1200 px.

Grid and spacing:

- 24-column grid with 16 px gutters.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48 px. Page padding is 24 px, and 16 px below 768 px.
- Forms are a single column, at most 640 px wide. Labels sit above fields.

Breakpoints:

| Name | Width | Behaviour |
|---|---|---|
| Phone | below 768 px | Side navigation collapsed; tables become cards; filters behind a Filters button |
| Tablet | 768 to 991 px | Side navigation collapsed; tables scroll horizontally if needed |
| Desktop | 992 px and above | Full layout |

Colours:

| Token | Value | Use |
|---|---|---|
| Primary | `#1677FF` | Primary buttons, links, selected items |
| Success | `#52C41A` | Approved, success messages |
| Warning | `#FAAD14` | Pending confirmation, warnings |
| Error | `#FF4D4F` | Denied, rejected, validation errors, destructive actions |
| Info | `#1677FF` | Pending approval, information messages |
| Neutral | `#8C8C8C` | Cancelled, secondary text |
| Text | `#1F1F1F` | Body text |
| Border | `#D9D9D9` | Field and table borders |
| Background | `#F5F5F5` | Page background; cards and tables are `#FFFFFF` |

Typography: system font stack (`-apple-system, "Segoe UI", Roboto, Arial, sans-serif`). Body 14 px with 22 px line height. Page title 24 px semibold, section title 16 px semibold. Corner radius 6 px.

## Components

| Component | Use |
|---|---|
| Button | Primary (one per screen), Default, Danger for destructive actions, Link for low-emphasis actions. Minimum height 32 px, 40 px on phones |
| Form field | Label above, optional help text below, error message below in the error colour. Required fields are marked with a red asterisk |
| Select | Choosing one item from a list, such as leave type or Project Manager. Searchable when the list has more than 10 items |
| Date range picker | Start and end date of a leave request. Days that cannot be chosen are disabled |
| Segmented control | Choosing the day part: All day, Morning, Afternoon |
| File upload | Drop area plus button. Lists each file with name, size, remove action and upload errors. States the allowed types and size |
| Table | Lists of requests, leave types and report rows. Sortable column headers, a row action column on the right, pagination below |
| Filter bar | Above a table: fields for request type, employee name, date range and status, with Apply and Reset |
| Status tag | The status of a leave request; see the mapping below |
| Card | One request on a phone, and summary figures on dashboards and reports |
| Descriptions list | Read-only details of one request as label and value pairs |
| Timeline | The history of a request: submitted, confirmed, approved, with who and when |
| Modal | Confirming an action, and entering a short input such as a reason. Never for long forms |
| Notification | Short success or failure message after an action, top right, closing after 4 seconds |
| Alert | In-page message: warning when a request exceeds the entitlement, error summary above a form, information banners |
| Empty state | Illustration, one sentence and, where useful, the action that fills the list |
| Skeleton | Placeholder while a page or table loads |
| Tabs | Switching between views of the same list, for example Needs my action and All |
| Pagination | Below tables: page numbers and page size of 20, 50 or 100 |

Status tag mapping:

| Status | Label | Colour |
|---|---|---|
| PENDING_CONFIRMATION | Pending confirmation | Warning |
| PENDING_APPROVAL | Pending approval | Info |
| APPROVED | Approved | Success |
| DENIED | Denied | Error |
| REJECTED | Rejected | Error |
| CANCELLED | Cancelled | Neutral |

A request that exceeds the entitlement also carries a Warning tag labelled "Exceeds entitlement".

## Patterns

Form validation:

- Validate a field when the user leaves it, and the whole form on submit.
- On submit with errors: show an error summary (Alert, error) above the form listing each problem as a link to its field, move focus to the summary, and show each message under its field.
- Messages say what is wrong and how to fix it: "Choose a start date in the future or in the current month."
- A warning does not block submission. It is shown as an Alert (warning) above the submit button and the user confirms in a Modal.

List with filters:

- The default view shows what needs the user's action. Filters and the chosen tab are kept in the URL.
- The filter bar shows how many results match. Reset returns to the default view.
- On a phone each row becomes a Card with the status tag at the top right.

Review a request:

- Open the request from the list into a detail page: Descriptions list, documents, Timeline, and the decision buttons in the page header.
- Confirm and Approve are primary buttons; Deny and Reject are Danger buttons. Each asks for confirmation in a Modal.
- After the decision, return to the list and show a Notification.

Destructive and irreversible actions:

- Cancelling a request and denying or rejecting one always ask for confirmation in a Modal that names the request and states the consequence.

Page states:

| State | What the user sees |
|---|---|
| Loading | Skeleton in the shape of the content |
| Empty | Empty state with a sentence that fits the context |
| Error | Alert (error) with a Retry button and the trace ID |
| No access | A page saying the user's role cannot open this area, with a link home |

Feedback after an action: a Notification for success; an Alert in the page for a failure the user must act on.

Dates and amounts: dates as `5 Jan 2026`; ranges as `5 – 9 Jan 2026`; leave amounts in days with halves, such as `2.5 days`.
