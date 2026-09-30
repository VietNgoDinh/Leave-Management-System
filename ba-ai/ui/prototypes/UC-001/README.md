---
id: UC-001
artifact_type: ui-prototype
title: Submit leave request — Interactive Prototype
status: WAITING_FOR_REVIEW
version: 1
baseline: TO_BE
origin: AI
relations:
  screens:
    - SCR-005
    - SCR-006
  business_rules:
    - BR-001
    - BR-002
    - BR-003
    - BR-004
    - BR-005
    - BR-007
    - BR-015
    - BR-017
    - BR-018
    - BR-021
    - BR-022
open_questions:
  - Q-026
  - Q-027
  - Q-028
  - Q-029
  - Q-016
  - Q-019
  - Q-022
  - Q-031
assumptions:
  - ASM-005
  - ASM-012
  - ASM-013
updated_at: '2026-09-30T09:59:05Z'
built_from:
  - path: ui/markdown/UC-001.md
    hash: 5c5d631a268e3644
  - ref: UC-001
    hash: da071cd16031e12f
  - ref: BR-001
    hash: b4a05b92418faf22
  - ref: BR-002
    hash: 7984c915f451dd06
  - ref: BR-003
    hash: d72de04c0af115d6
  - ref: BR-004
    hash: b5d4f8d2c9d30cfa
  - ref: BR-005
    hash: f43a351363c42a5e
  - ref: BR-007
    hash: 0355888b987d9bb6
  - ref: BR-015
    hash: 8270e1663344fc81
  - ref: BR-017
    hash: 73e86de911f31a94
  - ref: BR-018
    hash: ee9aa4c9ecbfd179
  - ref: BR-021
    hash: fb1152c1fac1c70a
  - ref: BR-022
    hash: aaf001a075179e3a
  - ref: Q-026
    hash: 8e8cd2b1e8f239de
  - ref: Q-027
    hash: f4d3f0d28951fbe4
  - ref: Q-028
    hash: 044dcf1ca779620c
  - ref: Q-029
    hash: 85a645b32d010871
  - ref: Q-016
    hash: aa76e4fa9c2fd001
  - ref: Q-019
    hash: ae9c693cefbc95e3
  - ref: Q-022
    hash: e433ebc178056ee8
  - ref: Q-031
    hash: becddc363513e38c
  - ref: ASM-005
    hash: 9022d0472d17ef86
  - ref: ASM-012
    hash: 597d0b73ab9b69f7
  - ref: ASM-013
    hash: 492c2b330b4eb6d7
review:
  GATE-04: WAITING
---
# UC-001 — Submit leave request: Interactive Prototype

Built from the functional UI `ba-ai/ui/markdown/UC-001.md` (approved at GATE-03). Where that document marks a behaviour as "pending Q-…", the prototype shows the assumed behaviour; the table under Assumed behaviours lists each one.

## How to Open
Open `ba-ai/ui/prototypes/UC-001/index.html` in a browser (double-click; no server needed).

The panel **Prototype controls** at the bottom right switches the signed-in user, forces the non-happy states and resets the data. A forced state stays on until it is set back to Normal or Success.

## Screens Covered
| Screen | Prototype route | Notes |
|---|---|---|
| SCR-005 Leave request form | `#/scr-005` | Includes the Exceeds entitlement dialog and the Discard dialog. All states: Loading, Empty, Initial, Populated, Exceeds entitlement, Validation error, Submitting, Server error, Session expired, No access |
| SCR-006 Leave request submitted | `#/scr-006/{requestId}` | States: Loading, Empty (not found or not the user's own), Populated, Server error, Success. Reloading the page in the same browser tab shows the request again |
| My leave requests (UC-002) | `#/my-leave-requests` | Placeholder: navigation target only |
| Leave request detail (UC-002) | `#/leave-request-detail/{requestId}` | Placeholder: navigation target only |
| Company single sign-on, Home, Reviews | `#/sso`, `#/home`, `#/reviews` | Placeholders for targets outside UC-001 |

## Sample Data
All people, projects, holidays and figures are fictional. The prototype's "today" is fixed at **30 Sep 2026**, so the current month is September 2026 and 1 Sep 2026 is the earliest date that can be chosen.

| Signed in as | Shows |
|---|---|
| Maya Okafor (default) | Employee in three projects with two Project Managers: Daniel Reyes appears once with two project names (BR-015). Paid Leave: 14 days entitlement, 11.5 days already requested, so a request of 3 days or more exceeds the entitlement. Her denied request of 3 days is not counted |
| Tomas Lindqvist | Employee in one project: the Project Manager is preselected. Male: Maternity Leave is listed but disabled with "For female employees only" (BR-004) |
| Daniel Reyes | Project Manager: no Project Manager field, automatic confirmation (BR-007) |
| Aiko Tanaka | Employee with no project: no confirmation step (BR-021) |
| Helen Brandt | Line Manager: no "Request leave" in the navigation, No access page on both screens |

| Leave type | Required documents | Note |
|---|---|---|
| Paid Leave | None | Entitlement differs per person (seniority, BR-003) |
| Sick Leave | Hospital certificate | 10 days |
| Maternity Leave | Hospital certificate, Maternity leave application | Female employees only |
| Bereavement Leave | None | 3 days |
| Unpaid Leave | None | Entitlement on record is 0 days, so every request is flagged (assumed behaviour pending Q-022) |

Public holidays: 21 Sep 2026 Harvest Day, 14 Oct 2026 Founders' Day, 19 Nov 2026 Unity Day, 25 Dec 2026 Winter Holiday, 1 Jan 2027 New Year's Day. Entitlements exist for 2026 only.

## Interactions
1. **Main flow, within the entitlement.** As Maya Okafor: choose Paid Leave, pick 29 Sep as first and last day, keep All day, choose a Project Manager. The Request summary shows 1 day, 14 days, 11.5 days, 1.5 days. Submit request: the button shows a loading indicator and the fields are locked, then SCR-006 opens with the Notification "Leave request submitted.", status Pending confirmation and the sentence naming the chosen Project Manager.
2. **Exceeds the entitlement (BR-002).** As Maya Okafor: Paid Leave, 28 to 30 Sep. The summary shows "Exceeds by 0.5 days" and the warning appears above the buttons. Submit request opens the dialog. Go back keeps the form. Submit request in the dialog opens SCR-006 with the warning and the tag "Exceeds entitlement".
3. **Validation errors.** On an empty form press Submit request: the error summary appears with focus on it, one link per problem, and each message under its field. Each link moves to its field. Leaving Leave type, Leave dates or Project Manager empty shows the field message on blur.
4. **Date rules (BR-001, BR-022).** Open the date picker: days before 1 Sep 2026 are disabled (previous-month arrow), weekends and the holiday 21 Sep are greyed and the holiday is named under the month. A range from Sat 26 to Sun 27 Sep gives "These dates contain no working day…". A range from 17 to 22 Sep counts 3 days (weekend and holiday are not counted).
5. **Day part (BR-017, assumed pending Q-026).** Pick a single day and choose Morning: 0.5 days. Extend the range to several days: Morning and Afternoon are disabled, the value returns to All day and the help text appears.
6. **Required documents (BR-005).** Choose Sick Leave and submit without a file: "Upload Hospital certificate. Sick Leave requires it." Add a file that is not PDF, JPG or PNG for the type error. In the controls set "files added are treated as" to Larger than 10 MB or Refused by the server and use "Attach sample files to empty upload fields" for the other two upload errors; set it to Normal and attach again for an accepted file. Remove empties the field.
7. **Leave type change removes files.** As Maya Okafor or Aiko Tanaka: choose Maternity Leave, attach sample files, then change to Sick Leave. The Hospital certificate is kept, the other file is removed and the information message appears.
8. **Project Manager's own request (BR-007).** As Daniel Reyes: the Reviewer section shows the automatic confirmation message. After submitting, SCR-006 shows Pending approval and that the Line Manager was notified (ASM-012).
9. **Employee with no project (BR-021).** As Aiko Tanaka: the Reviewer section shows the no-confirmation message. After submitting, SCR-006 shows Pending approval.
10. **Ineligible leave type (BR-004).** As Tomas Lindqvist: Maternity Leave cannot be chosen. For the server check, set "result of Submit request" to "Server rejects the leave type" and submit a valid form.
11. **Server rejections.** "Server rejects the start date (BR-001)" and "Server rejects the Project Manager (BR-015)" show the field message and the error summary after the submission. "Server error 503: nothing saved" shows the Alert with a trace ID above the form; values and files are kept.
12. **Server finds the request exceeds the entitlement (BR-002).** Set "result of Submit request" to that option and submit a request the form did not warn about: SCR-006 shows the warning and the tag.
13. **Submitting state.** Set "result of Submit request" to "Submitting (keep waiting)" and submit. Choose another result to let the submission finish.
14. **Cancel.** On an untouched form Cancel opens My leave requests. After entering something it opens the Discard dialog: Keep editing keeps the form, Discard leaves without saving.
15. **Form load states.** "SCR-005: form load": Loading keeps the skeleton, Empty shows "No leave types are available yet…", Server error shows the Alert with Retry and a trace ID. Retry loads the form again with the current setting; setting it back to Normal loads the form.
16. **No entitlement on record (assumed pending Q-016).** Tick "No entitlement on record" and choose a leave type and dates: the summary shows "No entitlement on record for {leave type} in {year}.", the amount counts as 0 days and the request can be submitted with the warning. The same appears without the control for a start date in 2027 (see Q-031).
17. **Session expired.** Press "Expire session now": the Notification appears, then the single sign-on placeholder opens and the form is empty when reopened.
18. **No access.** As Helen Brandt open `#/scr-005`: the No access page with a link home.
19. **SCR-006 states.** "SCR-006: page load": Loading, Server error (with Retry and a trace ID) and Request not found. Switching the signed-in user while on SCR-006 also shows "We could not find this leave request." because the request is not that user's own.
20. **SCR-006 actions.** View my leave requests and View this request open the UC-002 placeholders. Request more leave opens an empty SCR-005.
21. **Reset.** "Reset data" removes the requests submitted in the prototype and sets all controls back.

## Assumed behaviours
| Pending | What the prototype does |
|---|---|
| Q-026 | Morning and Afternoon only for a single day; a longer range is All day |
| Q-027 | Already requested counts Pending confirmation, Pending approval and Approved requests, including those submitted in the prototype. The whole request is counted against the year of its start date |
| Q-028 | No overlap check and no message about overlapping requests |
| Q-029 | Exactly one file per required document; no upload field when none is required |
| Q-016 | "No entitlement on record", counted as 0 days, request can be submitted with the warning |
| Q-019 | The earliest date and the review deadline are treated as given by the server; the prototype uses fixed sample values |
| Q-022 | Every leave type is checked against its entitlement, including Unpaid Leave |
| ASM-005, ASM-012, ASM-013 | Status labels; the Line Manager is emailed when confirmation is skipped; weekends are Saturday and Sunday |

## Limitations
- Nothing is sent or stored on a server. Load, upload and submission are simulated with short delays; emails are only mentioned in the texts. Submitted requests live in the browser tab (session storage) until "Reset data" or until the tab is closed.
- Files are not read or uploaded: only the name and the size are used. No malware scan.
- "Today" is fixed at 30 Sep 2026. Time zones are not represented (Q-019).
- The Select fields are not searchable: no list has more than 10 items.
- My leave requests, the request detail, single sign-on, Home and Reviews are placeholders. Sign out does nothing.
- The status on SCR-006 never changes, because confirming, approving and cancelling belong to other use cases.
- Gap found, raised as **Q-031**: a request that starts in the next year has no entitlement until the annual refresh, so the rule for a missing entitlement flags every such request as exceeding. The prototype shows this for dates in 2027.
- Gap in the functional UI, to confirm at review: the message "The required documents changed with the leave type…" is defined as an Alert in Supporting documents, but that section is hidden when the new leave type requires no document. The prototype then shows the section with the message only.
- Wording not defined in the functional UI and taken from the design system patterns: the No access page ("No access", "Your role cannot open this area.", "Go to home"), the Select placeholder "Select", the upload area text "Drop a file here or" with the button "Choose file", and the calendar legend.
- The text colour Warning (`#FAAD14`) used for "Exceeds by N days" has low contrast on white. It is shown with a warning icon and in bold, as specified.
