# RetailEdge EdgeSuite Reconciliation Oversight — Phase 4

## Business goal

Provide a clearer, faster and safer management view of reconciliation readiness, ERPNext handoff and unmatched payment-event evidence without adding any reconciliation or accounting action to the EdgeSuite UI layer.

This phase helps users understand what is ready, what is blocked and what needs investigation. It does not perform the corrective work.

## Product layer

- Product app: RetailEdge
- Shared presentation: EdgeSuite UI Query Report adapter
- Accounting and reconciliation authority: native ERPNext and existing RetailEdge backend workflows

## Reports migrated

1. RetailEdge Bank Match Reconciliation Readiness
2. RetailEdge Reconciliation Handoff
3. RetailEdge Unmatched Bank Payment Events

## Shared behaviour

Each report now uses the existing RetailEdge shared report adapter to provide:

- EdgeSuite business header;
- compact active-filter context;
- selected native KPI cards;
- current-view status;
- evidence-based recommendations;
- useful empty-state guidance;
- native Frappe Query Report fallback.

Existing tables, filters, links, result limits, operational refresh, export and print remain unchanged.

## Reconciliation Readiness

The report continues to use the existing readiness rows and statuses.

The EdgeSuite layer highlights:

- ready rows;
- rows needing review;
- exceptions and not-ready rows;
- unresolved canonical bank or payment account context;
- confirmed matches remaining outside the ready queue for three days or more.

This report does not confirm matches or reconcile transactions.

## Reconciliation Handoff

The report continues to use the existing handoff provider and native summary.

The EdgeSuite layer highlights:

- rows ready for controlled ERPNext reconciliation;
- rows requiring review;
- exceptions;
- recorded blocking reasons;
- missing candidate document evidence;
- high-priority rows that are not ready.

Any ready-row recommendation explicitly directs users to the normal permission-controlled ERPNext reconciliation flow. No action is executed by this report.

## Unmatched Bank Payment Events

The report continues to expose unmatched Payment Entries, Invoice Payment Rows and POS Payment Rows.

The EdgeSuite layer highlights:

- payment-account or canonical-account gaps;
- events without candidate Bank Transactions;
- events outstanding for seven days or more;
- recorded reasons or exceptions;
- source events without transaction or payment-row references.

The report does not create a Bank Match Review or select a candidate automatically.

## Safety boundaries

This phase adds no endpoint or action for:

- creating a Bank Match Review;
- confirming or rejecting a suggested match;
- reconciling a Bank Transaction;
- creating a Payment Entry;
- creating a Journal Entry;
- changing a Sales Invoice or payment row;
- changing reconciliation status;
- posting to GL or stock;
- submitting, cancelling or deleting a document.

The report modules contain explicit regression coverage against these operations.

## Files changed

- Reconciliation Readiness report Python and JavaScript
- Reconciliation Handoff report Python and JavaScript
- Unmatched Bank Payment Events report Python and JavaScript
- focused reconciliation oversight test module
- this implementation note

## Migration and backward compatibility

- No DocType field is added or changed.
- No database patch or migration is introduced.
- Existing report names and routes remain stable.
- Existing report filters, columns and links remain stable.
- Existing permission and branch/company filtering remains authoritative.
- Native Frappe summary fallback remains available if EdgeSuite UI cannot mount.

## Automated tests required

The focused test module covers:

- shared adapter registration and refresh attachment;
- preservation of report filter definitions;
- readiness exception, account and ageing recommendations;
- handoff blocker, priority and candidate recommendations;
- unmatched payment-event context, candidate, ageing, exception and reference recommendations;
- absence of document-write and reconciliation-action calls.

Full Frappe tests, builds and migration must run after the private EdgeSuite UI dependency can be checked out in CI.

## Manual QA gate

After clean CI, verify each report with real permitted data:

1. Company, branch, date and report-specific filters.
2. Native KPI totals against table rows.
3. Recommendations for mixed ready, blocked and exception rows.
4. Direct links to Bank Transactions, Bank Match Reviews and candidate documents.
5. Empty-state behaviour.
6. Export and print.
7. Native fallback if the shared runtime is unavailable.
8. Branch and company permission isolation.
9. Desktop and mobile layouts.

## Deferred work

The following still require a later operational phase and stronger QA:

- review creation and confirmation screens;
- actual ERPNext reconciliation actions;
- payment and journal creation;
- Cashier Expense operational form migration;
- POS shift and Daily Sales Audit workflow actions;
- any stock or ledger posting workflow.

## CI dependency

The RetailEdge repository still requires `EDGESUITE_UI_TOKEN` with read-only Contents access to the private `olayemigod/processedge-edge-suite-ui` repository.

The dependency must not be replaced with copied shared assets, duplicated components or a fake CI-only app.
