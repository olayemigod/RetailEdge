# RetailEdge Action Centre Browser QA

Use this checklist on `retail.local` before promoting `/app/action-center` into normal RetailEdge navigation.

## Preconditions

- Pull the latest `agent/r2-usability-foundation` branch.
- Build assets and migrate the site.
- Confirm the `RetailEdge Action Follow Up` DocType exists.
- Use test users representing System Manager, RetailEdge Manager/Branch Manager/Auditor, Accounts Manager, Stock Manager, and at least one ordinary operational user without an Action Centre page role.
- Ensure the site contains at least one visible critical or warning exception from an existing RetailEdge/ERPNext source.

## Shell and access

1. Open `/app/action-center` as System Manager and confirm the EdgeSuite shell loads with no competing native sidebar.
2. Repeat with RetailEdge Manager, RetailEdge Branch Manager, RetailEdge Auditor, Accounts Manager and Stock Manager as applicable.
3. Confirm an ordinary user without an allowed Page role cannot open the Action Centre route.
4. Confirm inaccessible exception sources are excluded rather than leaking counts, labels or data.
5. Confirm company and branch scope match the signed-in user's permitted context.

## Exception truth and drill-through

1. Compare every visible exception against its owning report/workflow and confirm count/value parity.
2. Use **Open workflow** and confirm it opens the authoritative RetailEdge/ERPNext process.
3. Confirm Action Centre itself does not submit, approve, cancel, reconcile, post, mutate stock, create accounting entries or otherwise resolve the underlying exception.
4. Resolve one underlying exception in its owning workflow, refresh Action Centre, and confirm the exception disappears or changes only according to the source-of-truth report.

## Follow-up persistence

For one visible exception:

1. Acknowledge it and refresh the browser; confirm the acknowledgement persists.
2. Assign it to another permitted user; confirm assignment persists after refresh.
3. Set a follow-up date without assigning it; confirm scheduling does not silently assign the item.
4. Add follow-up notes, then acknowledge/reopen the item; confirm notes are preserved unless explicitly edited.
5. Snooze the item to a future time and confirm effective status is Snoozed.
6. Reopen it and confirm effective status returns to Open without changing the underlying business exception.
7. Confirm follow-up changes never change Sales Invoice, Purchase Invoice, Payment Entry, Stock Entry, Expense Review, Cash Shift or other owning business documents.

## Management views

1. Test **Follow-up Status**: All, Open, Acknowledged and Snoozed.
2. Test **Assignment**: All Actions and My Actions.
3. Test **Timing**: All Timing and Due / Overdue.
4. Confirm summary cards/counts refresh from the server after every follow-up mutation.
5. Confirm a future snoozed item is not treated as due while the snooze is active.
6. After the snooze time passes, refresh and confirm the item becomes effectively Open without requiring a background database mutation.
7. Confirm an expired snooze can appear in Due / Overdue when its follow-up date is due.

## UX and responsive QA

1. Check Light and Dark appearance modes for readable text, borders, status pills, dialogs and buttons.
2. Check desktop, tablet and narrow mobile widths.
3. Confirm action buttons wrap cleanly and remain usable without horizontal overflow.
4. Confirm Frappe assignment, schedule and snooze dialogs appear above the Action Centre shell and are keyboard usable.
5. Confirm long exception labels, usernames and notes do not break card layout.
6. Confirm loading, empty, partial-permission and backend-error states are understandable.

## Promotion gate

Do not add Action Centre to normal RetailEdge navigation until:

- CI and Linters are green on the exact promotion head.
- This browser QA passes for management/control roles and a denied ordinary user.
- Exception values are verified against their owning reports/workflows.
- Follow-up persistence survives browser refresh and does not mutate business truth.
- Dark mode and mobile layout are acceptable.
- Navigation uses a reusable item-level role/permission gate rather than exposing the Page to the whole Review & Approvals group.
