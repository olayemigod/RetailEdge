# RetailEdge EdgeSuite UI Migration

## Phase 1 — Consumer foundation and Home

The first RetailEdge EdgeSuite UI slice is implemented on `agent/retailedge-edgeui-foundation`.

It establishes:

- a required local `edgesuite_ui` dependency;
- a RetailEdge app launcher route at `/app/retailedge-home`;
- a source-controlled RetailEdge launcher icon;
- a product-owned Vue application factory using `runtime.install(app)`;
- EdgeSuite UI 0.5+ runtime and component validation;
- tenant, company, user and branch identity in Frappe boot context;
- a RetailEdge navigation adapter and searchable product menu;
- a permission-aware Home context provider;
- a source-controlled RetailEdge Home page;
- the existing `/app/retailedge` workspace as a native fallback.

The implementation targets the current shared document-foundation branch:

```text
olayemigod/processedge-edge-suite-ui
agent/edgeui-document-foundation
```

The branch currently exposes EdgeSuite UI 0.5.4 even though its draft PR originally described the work as 0.5.0.

The separate EdgeSuite UI primary-menu branch has not been consolidated into the document foundation. RetailEdge Home is therefore the first normal product-menu section in this phase. It should be promoted to the dedicated `primary_item` contract only after that shared feature is merged and validated, avoiding duplicate Home entries.

## Phase 2 — Native Query Report enhancement

The second slice is implemented on the stacked branch `agent/retailedge-edgeui-report-adapter`.

It introduces one reusable `retailedge_report_edgeui.js` adapter and applies it to:

1. RetailEdge Branch Performance Summary;
2. RetailEdge Cashier Expense Review;
3. RetailEdge Daily Sales Audit Register.

The adapter replaces only the visual summary area. It preserves:

- each report's existing Python query and permission-aware branch filtering;
- the native Frappe Query Report filter controls;
- the native DataTable, chart, document links and drill-down behaviour;
- native export and print behaviour;
- the existing auto-refresh and prepared-report safeguards;
- all ERPNext accounting and stock documents.

The report server returns an internal EdgeSuite metadata marker alongside normal Frappe summary cards. When the shared runtime is available, the adapter removes the marker, renders the selected KPI cards, filter context, recommendations and empty state, and hides the duplicate native summary. If the adapter cannot mount, the metadata marker is removed and the normal Frappe summary remains visible.

The pilot reports add the following decision support:

- **Branch Performance:** sales, cashier expenses, net cash expected, outstanding balances, audit variance and payment exceptions;
- **Cashier Expense Review:** pending review, clarification, pending ledger and posting-blocked expense controls;
- **Daily Sales Audit Register:** cash sales, expected and actual closing cash, absolute variance, reviewer action and clarification requirements.

No report client or metadata helper creates, updates, submits, cancels or deletes a business document.

## Safety boundaries

These phases do not create a generic write API and do not migrate operational or accounting documents.

They do not mutate:

- Sales Invoice;
- Payment Entry;
- Bank Transaction;
- Journal Entry;
- Stock Entry;
- Stock Reconciliation;
- POS Opening Shift;
- POS Closing Shift;
- submitted accounting or stock documents.

Home items are returned only when the configured target exists and the current user has read permission.

The Home branch selector is a context preview in this phase. It does not filter linked reports, change User Defaults, switch CoreEdge runtime context, change ERPNext defaults or alter document attribution.

## Dependency and CI gate

RetailEdge CI checks out the private EdgeSuite UI repository using:

```text
EDGESUITE_UI_TOKEN
```

That repository secret must be configured before the clean Frappe v16 install, asset build and migration job can pass.

The current GitHub linter workflow passes on the foundation branch. Full CI stops at the private EdgeSuite UI checkout step, before bench setup, builds, migration or RetailEdge tests run.

This dependency must not be replaced with a copied CoreEdge frontend path, a fake CI-only app or a locally duplicated EdgeSuite component set.

## Manual QA gate

Manual QA is deferred until an operator is available. Before the stacked phases are merged, verify:

1. RetailEdge launcher visibility for permitted and unpermitted users.
2. Product-menu mounting and navigation.
3. RetailEdge Home on desktop and mobile.
4. Company and branch identity.
5. Cashier, Branch Manager, Auditor, Accounts and Administrator permission views.
6. Native ERPNext DocType and Query Report links.
7. Native Frappe sidebar restoration after leaving the EdgeSuite page.
8. One-branch, multi-branch and no-Branch configurations.
9. Slow-network and asset-load failure behaviour.
10. EdgeSuite headers and KPI cards on the three pilot reports.
11. Native report filters, tables, charts, links, export and print after the adapter mounts.
12. Native report summary fallback when the shared runtime is intentionally unavailable.
13. Real branch data totals against the underlying Query Report rows.

## Next implementation slices

After the foundation and report adapter pass build, migration and browser QA:

1. Migrate Salesperson Performance to the shared app factory, Link fields and branch context.
2. Pilot the full document workspace with safe RetailEdge-owned documents such as Branch Profile, Settings and Cashier Expense.
3. Add a safe master workspace for Expense Category and Statement Mapping Template.
4. Extend the proven report adapter to the bank matching, reconciliation, stock and receivables/payables reports.
5. Build the dedicated Bank Reconciliation Centre after the shared provider contracts are stable.
