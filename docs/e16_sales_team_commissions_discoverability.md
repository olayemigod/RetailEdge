# E16 C25 — Sales Team, Targets & Commissions Discoverability

## Goal

Close the remaining sales-management discoverability gap by exposing ERPNext v16's native Sales Person, Sales Partner, commission-summary and target-variance capabilities through the existing EdgeSuite business navigation.

## Context

RetailEdge already has a Salesperson Performance dashboard, Professional Selling, pricing/promotions, customer credit and loyalty capabilities. Those remain unchanged. C25 does not create another commission engine or salesperson ledger.

ERPNext v16 remains authoritative for:

- Sales Person hierarchy, employee link, commission rate and target allocation;
- Sales Partner master data, commission rate and target allocation;
- Sales Team contribution rows on selling transactions;
- Sales Person Commission Summary;
- Sales Partner Commission Summary;
- Sales Person Target Variance Based On Item Group;
- Sales Partner Target Variance based on Item Group;
- any native Selling Settings controlling commission tracking;
- any downstream payroll, payable or payment treatment outside this navigation slice.

## Scope

Expose the following native destinations under the existing **Sell** group:

1. Sales Person
2. Sales Partner
3. Sales Person Commission Summary
4. Sales Partner Commission Summary
5. Sales Person Target Variance Based On Item Group
6. Sales Partner Target Variance based on Item Group

Each destination must continue through RetailEdge's existing permission-aware navigation resolver:

- DocTypes require existence plus current-user `read` permission;
- Reports require existence plus Frappe's native report permission gate;
- missing or unavailable native targets are hidden independently;
- there is no hard-coded RetailEdge role override.

## Out of Scope

C25 must not add:

- a RetailEdge commission DocType, ledger, wallet or payout register;
- automatic commission accrual or settlement;
- Additional Salary, Salary Slip, Payment Entry or Purchase Invoice creation;
- automatic Sales Person/Sales Partner assignment;
- submitted Sales Order, Delivery Note or Sales Invoice mutation;
- direct GL Entry or Stock Ledger Entry writes;
- manual database commits or `ignore_permissions`;
- schema changes, migrations or data patches.

## Safety Contract

RetailEdge only improves discoverability. ERPNext continues to own contribution, commission, target and report calculations. A user who cannot open a native target must not see it through EdgeSuite. This slice introduces no accounting or payroll side effect and no optional-app hard dependency.

## Validation

Required validation at the exact C25 head:

- focused C25 navigation contract tests;
- full RetailEdge test suite;
- RetailEdge Theme Compatibility;
- Linters, Semgrep and vulnerable-dependency audit;
- clean Frappe v16 CI;
- governed EdgeSuite UI Candidate Compatibility.

Manual browser QA remains deferred to the consolidated QA line.
