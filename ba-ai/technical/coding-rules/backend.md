---
id: CODING-BACKEND
artifact_type: coding-rules
title: Backend Coding Rules
status: APPROVED
version: 1
baseline: TO_BE
origin: AI
updated_at: 2026-09-30 09:12:44+00:00
review:
  GATE-09: APPROVED
---
# Backend Coding Rules

Java 21 and Spring Boot 3, in the repository REPO-001. The architecture document defines the modules and the API conventions; these rules cover how code inside a module is written.

## Conventions

Structure:

- One top-level package per module. Inside it: `api`, `application`, `domain`, `infrastructure`.
- Controllers contain no business logic. They map a request to one application service call.
- Application services own transactions (`@Transactional`) and authorization checks.
- Business rules live in the domain package as plain Java, without framework annotations. Each rule is one method or class named after what it checks, with the rule ID in its Javadoc.
- A module calls another module only through its public interface. Repositories and entities are package-private to their module.

Naming:

- Classes: `LeaveRequestController`, `SubmitLeaveRequestService`, `LeaveRequestRepository`.
- DTOs end in `Request` or `Response`. JPA entities are never returned from a controller.
- Database tables and columns are snake_case; one Flyway script per change, named `V<number>__<description>.sql`. Scripts are never edited after they are merged.

State and data:

- The leave request status changes only through methods on the entity that enforce the allowed transitions. An invalid transition throws a domain exception mapped to 409.
- Every entity that can be edited has a `version` column for optimistic locking.
- Dates use `LocalDate`, timestamps use `Instant`. The current time comes from an injected `Clock`.
- Money-like and day amounts use `BigDecimal`; leave days are multiples of 0.5.

Errors:

- Domain exceptions carry a stable error code. One `@RestControllerAdvice` turns them into problem details responses.
- Never catch and ignore an exception. Never return `null` from a public method; use `Optional` or an empty collection.

Integrations and jobs:

- Each external system is reached through an interface in the module and an adapter in `infrastructure`.
- A scheduled job is a thin class that calls an application service. It takes a ShedLock lock, processes in batches, and can be re-run safely after a failure.
- Emails are written to the outbox in the same transaction as the change that causes them.

Quality:

- Code is formatted with the project formatter and passes static analysis in the build.
- Public application services and domain rules have unit tests. New endpoints have an integration test for the success path and for each error status they can return.
