# E16 C26 — Budgeting & Cost Control Discoverability

## Goal

Close the formal budgeting and budget-vs-actual discoverability gap without introducing a RetailEdge budget ledger or replacing ERPNext's native budget controls.

## Competitive Context

Current accounting suites such as Zoho Books and QuickBooks expose formal budgets and budget-vs-actual review as standard financial-planning capabilities. RetailEdge already provides operational dashboards, cash outlook, branch performance and R8–R12 intelligence, but its EdgeSuite business navigation did not expose ERPNext's native budgeting controls.

## ERPNext Authority

ERPNext v16 remains the source of truth for:

- the submitted `Budget` document;
- Company and fiscal-year scope;
- budgets against Cost Center or Project;
- Budget Account and amount;
- monthly, quarterly, half-yearly or yearly distribution;
- budget distribution rows;
- Stop / Warn / Ignore controls for Material Requests;
- Stop / Warn / Ignore controls for Purchase Orders;
- controls against actual booked expenses;
- cumulative expense controls;
- Cost Center hierarchy and Company ownership;
- `Budget Variance Report` calculations, dimensions, periods and cumulative display.

RetailEdge must not reinterpret those calculations or enforcement rules.

## Scope

Expose the following native ERPNext destinations in the existing **Accounting** group:

1. `Budget`
2. `Budget Variance Report`
3. `Cost Center`

The existing Accounting group access contract remains unchanged: Accounts User, Accounts Manager and System Manager enter the group, and each native destination is then filtered by the existing DocType/read or native report permission gate. This is intentionally no broader than the current Accounting navigation.

## Relationship to Existing RetailEdge Programmes

### R8–R12 intelligence

R12 remains the owner of behavioural forecasting, scenarios and forecast-vs-actual intelligence. An ERPNext Budget is a formal plan/control baseline; it is not a replacement cash-flow forecasting engine.

### Project Operations

Project Operations remains the owner of project receipts, project expenses, project funds and operational project workflows. ERPNext Budget may natively budget against Project, but C26 does not create a second project-funds model. Any future linkage must consume the same ERPNext Project/Budget truth rather than duplicate it.

### Branch operations

C26 does not fabricate Branch-level budgets. Where ProcessEdge deployments model operational responsibility through Cost Centers, Projects or accounting dimensions, ERPNext remains authoritative for that setup and validation.

## Out of Scope

C26 must not add:

- a RetailEdge Budget DocType or child table;
- a shadow budget ledger or wallet;
- automatic budget creation from forecasts;
- automatic budget creation from Project Operations;
- browser-side budget enforcement;
- direct Budget submission or cancellation from a RetailEdge API;
- mutation of submitted Budgets outside native ERPNext amendment rules;
- custom GL Entry or Stock Ledger Entry writes;
- manual database commits or `ignore_permissions`;
- schema changes, migrations or data patches.

## Safety Contract

RetailEdge only improves discoverability. ERPNext continues to own Budget creation, submission, amendment, enforcement and variance calculations. Existing accounting and native ERPNext permissions remain in force, and no accounting truth is copied into a second RetailEdge planning store.

## Validation

Required validation at the exact C26 head:

- focused C26 navigation contract tests;
- full RetailEdge test suite;
- RetailEdge Theme Compatibility;
- Linters, Semgrep and vulnerable-dependency audit;
- clean Frappe v16 CI;
- governed EdgeSuite UI Candidate Compatibility.

Manual browser QA remains deferred to the consolidated QA line.
