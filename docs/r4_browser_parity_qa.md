# RetailEdge R4 Browser and Parity QA Gate

This is the single local QA runbook for closing R4 and deciding whether the remaining EdgeSuite preview pages can become primary navigation.

## Preconditions

- Use the exact PR #23 head being validated.
- `git status` must be clean after pull/build/migrate.
- Build RetailEdge and EdgeSuite UI assets.
- Run `bench --site retail.local migrate`.
- Confirm CI and Linters are green on the same commit.
- Keep browser console and network panel open while testing.

## 1. Action Centre — closure QA

Action Centre is already role-gated in EdgeSuite `Review & Approvals`. This QA validates that promoted experience; it must not broaden access.

Verify:

- EdgeSuite single shell; no competing native sidebar.
- Allowed management/control users can open it; an ordinary denied user cannot and does not receive the menu item.
- Company/Branch scope and source permissions are respected.
- Receivables, Payables, Stock and Bank/Reconciliation exception values agree with their owning reports/services.
- `Open workflow` reaches the authoritative owning process.
- No Action Centre control submits, approves, reconciles, posts or mutates the underlying business document.
- Acknowledge, Assign, Follow-up, Snooze and Reopen persist after refresh.
- Scheduling alone does not silently assign an action.
- Existing notes survive unrelated acknowledgement/reopen actions.
- Snooze expiry and Due/Overdue behavior are correct.
- Critical > due follow-up > age > comparable financial exposure ordering is visibly correct.
- `Why this is prioritised` matches the server reason; no numeric priority score is shown.
- Light/Dark, desktop/tablet/mobile and dialog layering are acceptable.

Record: PASS / FAIL and screenshots or concise notes for any failure.

## 2. Stock Movement History — promotion candidate

Compare `/app/stock-movement-history` against `RetailEdge Stock Movement History` using the same Company, Branch, Warehouse, Item and date range.

Verify:

- opening balance parity;
- Stock Reconciliation treatment parity;
- quantity in/out and running balance parity;
- voucher links open the correct source documents;
- Company/Branch/Warehouse cascades clear invalid dependent values;
- 25/50/100 pagination behaves correctly;
- a scope above 1,000 raw Stock Ledger rows is blocked rather than silently truncated;
- CSV/Excel/Print-PDF use the shared EdgeSuite export menu;
- export contains the complete bounded filtered dataset, not only the current page;
- no duplicate native sidebar;
- Light/Dark and mobile layouts are usable.

Promotion rule: switch primary Stock Movement navigation to Page `stock-movement-history` only after all parity and browser checks pass. Retain the Query Report as **Detailed Report** after promotion.

## 3. Expense Review — promotion candidate

Compare `/app/expense-review` against `RetailEdge Cashier Expense Review` for the same Company/Branch/date/review filters.

Verify:

- row count and review-status parity;
- summary parity;
- Include / Exclude / Needs Clarification actions produce the same authoritative workflow result as the existing review engine;
- users without reviewer permission remain read-only;
- no action uses permission bypass or submits accounting documents;
- filters are bounded and Link fields show only relevant permitted records;
- export uses the shared EdgeSuite reporting path;
- dialogs appear above the shell;
- Light/Dark and mobile layouts are usable.

Promotion rule: replace the primary `Cashier Expense Review` report target with Page `expense-review` only after PASS. Keep the existing report as a detailed fallback.

## 4. Cash Shift Verification — promotion candidate

Compare `/app/cash-shift-verification` against `RetailEdge Cash Shift Verification` for identical scope.

Verify:

- row and exception-count parity;
- shortages, overages, missing shifts and review exceptions match the legacy report;
- the page does not alter POS shifts, payments, expenses or ledger entries;
- the 1,000-row guard blocks over-broad scopes instead of truncating silently;
- pagination, filters and drill-through work;
- partial-permission and empty states are understandable;
- Light/Dark and mobile layouts are usable.

Promotion rule: switch the primary target to Page `cash-shift-verification` only after PASS, preserving the Query Report as detailed fallback.

## 5. Daily Sales Audit — promotion candidate

Compare `/app/daily-sales-audit` against the native `RetailEdge Daily Sales Audit` list and `RetailEdge Daily Sales Audit Register` report for identical filters.

Verify:

- audit row and status/result parity;
- Review Required, Clarification Required and Net Variance summaries match source records;
- Company → Branch and Company → POS Profile filtering is correct;
- Cashier options contain only enabled users and remain permission-safe;
- row drill-through opens the correct Daily Sales Audit/User/POS Profile/shift records;
- the 1,000-row guard blocks over-broad scope;
- pagination and shared export are correct;
- no review/accounting mutation occurs from the read-only report page;
- Light/Dark and mobile layouts are usable.

Promotion rule: switch the primary `Daily Sales Audit` operating view to Page `daily-sales-audit` only after PASS. Retain the DocType/list and register as explicit detailed/record-management destinations.

## Promotion record

For each surface record:

| Surface | Automated CI | Browser shell | Source parity | Role/permission | Mobile/Dark | Promotion |
| --- | --- | --- | --- | --- | --- | --- |
| Action Centre | Required | Required | Required | Required | Required | Already role-gated; close R4 when PASS |
| Stock Movement History | Required | Required | Required | Required | Required | Keep legacy until PASS |
| Expense Review | Required | Required | Required | Required | Required | Keep legacy until PASS |
| Cash Shift Verification | Required | Required | Required | Required | Required | Keep legacy until PASS |
| Daily Sales Audit | Required | Required | Required | Required | Required | Keep legacy until PASS |

Do not mark a preview as promoted because its source tests are green alone. Browser rendering, parity and permission behavior must also pass on `retail.local`.
