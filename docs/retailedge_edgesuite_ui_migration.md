# RetailEdge EdgeSuite UI Migration

## Current implementation

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

## Safety boundaries

This phase does not create a generic write API and does not migrate operational or accounting documents.

It does not mutate:

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

The branch selector is a Home context preview in this phase. It does not filter linked reports, change User Defaults, switch CoreEdge runtime context, change ERPNext defaults or alter document attribution.

## Dependency and CI gate

RetailEdge CI checks out the private EdgeSuite UI repository using:

```text
EDGESUITE_UI_TOKEN
```

That repository secret must be configured before the clean Frappe v16 install, asset build and migration job can pass.

The current GitHub linter workflow passes. The full CI workflow stops at the private EdgeSuite UI checkout step, before bench setup, builds, migration or RetailEdge tests run.

This dependency must not be replaced with a copied CoreEdge frontend path, a fake CI-only app or a locally duplicated EdgeSuite component set.

## Manual QA gate

Manual QA is deferred until an operator is available. Before merge, verify:

1. RetailEdge launcher visibility for permitted and unpermitted users.
2. Product-menu mounting and navigation.
3. RetailEdge Home on desktop and mobile.
4. Company and branch identity.
5. Cashier, Branch Manager, Auditor, Accounts and Administrator permission views.
6. Native ERPNext DocType and Query Report links.
7. Native Frappe sidebar restoration after leaving the EdgeSuite page.
8. One-branch, multi-branch and no-Branch configurations.
9. Slow-network and asset-load failure behaviour.

## Next implementation slices

After this foundation passes build, migration and browser QA:

1. Add a reusable RetailEdge EdgeSuite report adapter while retaining native Query Report tables.
2. Migrate Salesperson Performance to the shared app factory, Link fields and branch context.
3. Pilot the full document workspace with safe RetailEdge-owned documents such as Branch Profile, Settings and Cashier Expense.
4. Add a safe master workspace for Expense Category and Statement Mapping Template.
5. Build the dedicated Bank Reconciliation Centre after the shared provider contracts are stable.
