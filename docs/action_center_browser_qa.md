# RetailEdge Action Centre Browser QA

Use this checklist on `retail.local` to complete the visual and interaction QA for the already role-gated EdgeSuite Action Centre navigation.

Action Centre is intentionally available in EdgeSuite `Review & Approvals` only to approved management/control roles. The purpose of this checklist is to validate that promoted experience before R4 is closed; it is not permission to broaden access or to promote the remaining QA-gated review pages.

## Preconditions

- Pull the latest `agent/r2-usability-foundation` branch.
- Build assets and migrate the site.
- Confirm the `RetailEdge Action Follow Up` DocType exists.
- Use test users representing System Manager, RetailEdge Manager/Branch Manager/Auditor, Accounts Manager, Stock Manager, and at least one ordinary operational user without an Action Centre page role.
- Ensure the site contains at least one visible critical or warning exception from existing RetailEdge/ERPNext sources, including financial, stock or banking exceptions where practical.

## Shell and access

1. Open `/app/action-center` as System Manager and confirm the EdgeSuite shell loads with no competing native sidebar.
2. Repeat with RetailEdge Manager, RetailEdge Branch Manager, RetailEdge Auditor, Accounts Manager and Stock Manager as applicable.
3. Confirm an ordinary user without an allowed Page role cannot open the Action Centre route and does not receive the navigation item.
4. Confirm inaccessible exception sources are excluded rather than leaking counts, labels or data.
5. Confirm company and branch scope match the signed-in user's permitted context.

## Exception truth, uniqueness and drill-through

1. Compare every visible exception against its owning report/workflow and confirm count/value parity.
2. Confirm each underlying business condition appears only once. In particular, verify that Receivables, Payables, Stock and Expense exceptions are not duplicated because the same condition also appears on Owner Dashboard.
3. Confirm Receivables/Payables exposure and ageing agree with their RetailEdge reports.
4. Confirm stock exception counts agree with Stock Position for the same Company/Branch scope.
5. Confirm banking actions agree with persisted Bank Transaction Match review/reconciliation state and do not trigger candidate discovery merely by loading Action Centre.
6. Use **Open workflow** on a RetailEdge Page target such as Expense Review, Customer Receivables, Supplier Payables, Stock Position or Cash Shift Verification. Confirm it stays in the current tab.
7. Use **Open workflow** on a retained native DocType or Query Report target such as Bank Transaction Match or a reconciliation report. Confirm it opens a new browser tab and leaves the Action Centre open in the original tab.
8. Confirm new-tab drill-through uses safe opener isolation and does not replace the current RetailEdge shell.
9. Confirm Action Centre itself does not submit, approve, cancel, reconcile, post, mutate stock, create accounting entries or otherwise resolve the underlying exception.
10. Resolve one underlying exception in its owning workflow, refresh Action Centre, and confirm the exception disappears or changes only according to the source-of-truth report.

## Prioritisation

1. Confirm Critical actions appear before Needs Attention actions.
2. Within the same severity, confirm due/overdue follow-ups appear ahead of otherwise comparable non-due actions.
3. Confirm older unresolved conditions can rise above newer conditions within the same severity/follow-up state.
4. Confirm the visible **Why this is prioritised** explanation matches the server ordering reason.
5. Confirm no numeric priority score is displayed or implied.

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

1. Check Light and Dark appearance modes for readable text, borders, status pills, dialogs, priority reason and buttons.
2. Check desktop, tablet and narrow mobile widths.
3. Confirm action buttons wrap cleanly and remain usable without horizontal overflow.
4. Confirm Frappe assignment, schedule and snooze dialogs appear above the Action Centre shell and are keyboard usable.
5. Confirm long exception labels, usernames, priority reasons and notes do not break card layout.
6. Confirm loading, empty, partial-permission and backend-error states are understandable.

## R4 closure gate

R4 Action Centre visual QA can be marked complete only when:

- CI and Linters are green on the exact head being tested.
- This browser QA passes for management/control roles and a denied ordinary user.
- Exception values are verified against their owning reports/workflows.
- No conceptual exception is duplicated across dashboard-derived and direct report sources.
- RetailEdge Page drill-through stays in the current tab and retained native DocType/Query Report drill-through opens safely in a new tab.
- Follow-up persistence survives browser refresh and does not mutate business truth.
- Priority ordering/reasons are visibly correct.
- Dark mode and mobile layout are acceptable.
- Navigation remains behind the reusable item-level role gate.

The following EdgeSuite pages remain separately QA-gated and must **not** be promoted as a side effect of Action Centre QA:

- `/app/stock-movement-history`
- `/app/expense-review`
- `/app/cash-shift-verification`
- `/app/daily-sales-audit`

Their existing legacy/native primary routes remain in force until each page completes its own source-parity and local browser QA.
