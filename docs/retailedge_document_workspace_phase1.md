# RetailEdge EdgeSuite Document Workspace — Phase 1

## Branch

`agent/retailedge-edgeui-document-workspace-phase1`

This phase is stacked on `agent/retailedge-edgeui-salesperson-dashboard`.

## Business goal

Give RetailEdge administrators and branch operators a guided setup experience without replacing Frappe metadata, permissions, DocType controllers or validation.

## Resources included

### Branch Profiles

The workspace supports permission-aware listing, search, filtering, creation and editing of `RetailEdge Branch Profile`.

Smart form behaviour includes:

- Company change clears Branch and all company-dependent POS, warehouse, account and cost-centre values.
- Branch change clears branch-sensitive POS Profile and warehouse values.
- Branch options are limited by Company and the user's branch access.
- POS Profile, Account, Warehouse and Cost Center options are limited to the selected Company when their schemas support Company.
- Account, Warehouse and Cost Center options exclude group records.
- User child rows return enabled System Users only.
- Cashier, Manager and Auditor table rows are normalised to the role represented by their parent table.
- Backend validation rejects cross-company linked records and inaccessible branches even if a browser request is forged.

Existing `RetailEdge Branch Profile.validate()` remains authoritative for duplicate active profiles and one default profile per Company.

### RetailEdge Settings

The workspace displays the single `RetailEdge Settings` document through `EdgeSettingsLayout` and metadata-derived tabs, sections, dependencies and child tables.

Only users with the native Settings read/write permissions can open or save it. At present, that is System Manager.

`RetailEdge Settings` has no Company field. Account lookups therefore use the user's active/default Company to avoid loading every account on the site. This preserves the current data model but remains a multi-company design limitation to revisit separately.

## Shared EdgeSuite components

- EdgeAppShell
- EdgePageLayout
- EdgePageHeader
- EdgeFilterBar
- EdgeDataTable
- EdgeDocumentForm
- EdgeWorkflowBar
- EdgeSettingsLayout
- EdgeLinkField
- EdgeLoadingState
- EdgeErrorState
- EdgeEmptyState

The product app owns all providers and permission checks. Shared EdgeSuite components do not call Frappe write APIs.

## Safety boundaries

This phase does not provide deletion, submission, cancellation, workflow transitions or a generic DocType API.

It does not write to Sales Invoice, Payment Entry, Bank Transaction, Journal Entry, Stock Entry, Stock Reconciliation or POS shifts.

Saves use normal `doc.insert()` or `doc.save()` and therefore retain native controller validation. Existing records use optimistic modified-timestamp checks.

Cashier Expense remains on its native form until this provider pattern has passed clean build, migration and browser QA.

## Discovery and native fallback

The RetailEdge product menu exposes `RetailEdge Setup Workspace`. Existing native Settings and Branch Profile links remain unchanged. Every workspace form provides an `Open native Frappe view` action.

## CI dependency

The RetailEdge repository still requires `EDGESUITE_UI_TOKEN` with read access to `olayemigod/processedge-edge-suite-ui`. Until it is configured, full CI stops before bench setup, asset builds, migration and Frappe tests.

## Manual QA gate

Manual QA is deferred. Before merge, verify:

1. Branch Profile list scope for Manager, Branch Manager, Auditor, Accounts and System Manager roles.
2. New and existing Branch Profile save behaviour.
3. Company and Branch cascade clearing.
4. Company filtering for POS Profiles, accounts, warehouses and cost centres.
5. Enabled-user child table searches and role normalisation.
6. Duplicate active/default profile validation from the native controller.
7. Settings dependencies and grouped navigation.
8. Optimistic-lock conflict messages.
9. Native form fallback and product-menu navigation.
10. Desktop and mobile layouts.
11. Visible failure behaviour when EdgeSuite assets are unavailable or outdated.
