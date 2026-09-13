# RIR2G2F2 — Sales Overview Date Cleanup

## Goal

Close the remaining confirmed raw date presentation leak in Sales Overview after G2F1.

## Scope

Only the Recent Invoices row in `SalesDashboard.vue` is in scope.

Current behavior exposes the raw backend `posting_date` string beside Customer.

Required correction:

- render the visible invoice date through Frappe user-date formatting;
- preserve the raw `posting_date` value in backend payloads and any future sort/filter logic;
- keep invoice identity, click behavior, dashboard calculations, filters and export/print behavior unchanged.

## Out of scope

- no backend API changes;
- no dashboard calculation changes;
- no date-input changes;
- no shared EdgeSuite UI runtime changes;
- no accounting, stock, workflow, permission or Branch-scope changes;
- do not reopen frozen G2F1.

## Freeze rule

Freeze only when Theme, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.