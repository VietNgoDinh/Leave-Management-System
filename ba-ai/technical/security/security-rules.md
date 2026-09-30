---
id: SECURITY
artifact_type: security-rules
title: Security Rules
status: APPROVED
version: 1
baseline: TO_BE
origin: AI
updated_at: 2026-09-30 09:12:44+00:00
assumptions:
  - ASM-014
review:
  GATE-09: APPROVED
---
# Security Rules

The system holds personal data: gender, leave history and medical documents. These rules apply to every use case.

## Authentication

- Users sign in through the company single sign-on with OpenID Connect, authorization code flow (INT-004, ASM-014). The system stores no passwords and has no sign-in form of its own.
- The backend performs the sign-in and keeps the session. The browser holds only a session cookie: `HttpOnly`, `Secure`, `SameSite=Lax`. Tokens never reach JavaScript.
- A session ends after 30 minutes without activity and at most 8 hours after sign-in. Sign-out ends the session here and at the single sign-on.
- Every request that changes data carries a CSRF token.
- A signed-in user who is not an active employee in the HR data gets no access.
- Scheduled jobs and integrations run under a system identity, never under a user's.

## Authorization

Roles come from the HR data: EMPLOYEE, PROJECT_MANAGER, LINE_MANAGER, ADMIN_HR. A user can hold several, except that a Line Manager is never a Project Manager (BR-019).

Access is denied unless a rule below allows it. The server checks every request; hiding a button is not a control.

| Data | Employee | Project Manager | Line Manager | Admin/HR |
|---|---|---|---|---|
| Leave request | Own: create, view, resubmit, cancel | Those that selected them: view, confirm, deny | Those of employees they manage: view, approve, reject | View all |
| Supporting document | Own | Of requests they can view | Of requests they can view | View all |
| Leave type | View | View | View | Create, edit |
| Leave entitlement | Own | None | Those of employees they manage | View all |
| Reports | None | None | Own unit only | All units |

- Access to one object is checked against that object, not only against the role. A request for an object outside the user's scope returns 404.
- A reviewer cannot decide on their own request. A Project Manager's own request is auto-confirmed (BR-007).
- Reporting scope follows the organisational unit the Line Manager manages (BR-014).

## Data Protection

- All traffic uses TLS 1.2 or later. The database, its backups and the object storage are encrypted at rest.
- Supporting documents are stored in object storage under random names. They are downloaded only through the API, after the access check.
- Uploads are limited to PDF, JPG and PNG, at most 10 MB each, and are scanned for malware before they become available.
- Personal data is never written to logs, URLs or error messages. Identifiers in URLs are random, not sequential.
- Secrets come from the platform's secret store, never from the repository or an image.
- Input is validated on the server. Database access uses parameterised queries only. Output is encoded by the framework; raw HTML from user input is never rendered.
- Emails contain no medical detail and no document: they name the request and link to the application.
- Production data is not copied to other environments without masking.
- How long leave requests and documents are kept is not defined yet and needs a decision from the client's compliance function before go-live.

## Audit

The system keeps an audit trail in the database, separate from application logs. Entries are only ever added.

Recorded events:

- every state change of a leave request, with the old and new status and the reason for a cancellation;
- every review decision, including automatic confirmation;
- creation and every change of a leave type and its rules, with the old and new values;
- every run of the annual entitlement refresh, the month-end cancellation and the HR sync, with counts;
- every download of a supporting document;
- every denied access attempt.

Each entry holds: when (UTC), who (employee ID or system identity), what (event type), which object (type and ID), and the trace ID.

Admin/HR can view the audit trail of a leave request. Nobody can edit or delete entries through the application.
