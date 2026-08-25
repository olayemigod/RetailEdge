# Phase 1 — Customer-Facing Terminology Cleanup

## Goal

Remove unnecessary `RetailEdge` prefixes and technical/internal wording from **all customer-facing RetailEdge surfaces** while preserving stable Frappe/ERPNext/RetailEdge internal identities, routes, DocTypes, reports, permissions, APIs, migrations, accounting truth, and multi-app coexistence.

This phase is presentation and terminology cleanup only. It must not rename internal DocTypes, fieldnames, APIs, roles, routes, or mutate business transactions.

## Baseline and branch strategy

- `version-16` remains the authoritative ancestor baseline.
- Current R2 usability foundation is directly ahead of `version-16` and contains the active professional single-shell UX.
- Implement Phase 1 on a dedicated branch from the current R2 foundation.
- Preserve all later stacked branches. Reconcile downstream stacks only after this phase is audited, validated, QA-approved, and promoted.

## Customer-facing naming principles

1. Do not repeat the product name when the user is already inside RetailEdge.
2. Prefer plain business terminology over package/framework terminology.
3. Keep internal package, DocType, fieldname, report, role, route, module, API, and database identities stable unless a separate migration is explicitly approved.
4. ERPNext remains the underlying system of record. Customer-facing labels may be friendlier, but they must not misrepresent accounting or stock semantics.
5. Customer-facing names should remain understandable when RetailEdge coexists with other ProcessEdge or third-party Frappe apps.
6. The terminology contract applies to every customer-visible string, not only links or navigation.

## Customer-facing surfaces in scope

Audit and normalize, where applicable:

- Workspace and sidebar labels
- EdgeSuite product-menu labels
- Page titles and headings
- Dashboard titles and KPI labels
- DocType field labels
- Section Break and Column Break labels
- Tab labels
- Child-table field labels
- Form descriptions and help text
- Dialog titles and field labels
- Guided-entry labels
- Buttons and actions
- Report titles shown to users
- Report filter labels
- Report column labels
- Empty-state text
- Loading/error messages
- Tooltips
- Validation and user-facing information messages
- Setup/configuration labels
- Print-facing labels where RetailEdge controls them
- Customer portal labels when that later phase is reconciled

Internal identifiers must not be renamed merely because their visible label changes.

## Initial terminology contract

| Internal / current target | Customer-facing label | Notes |
| --- | --- | --- |
| RetailEdge Business Hub | Business Hub | Product context already says RetailEdge. |
| RetailEdge Settings | Settings | Internal DocType stays `RetailEdge Settings`. |
| RetailEdge Branch Profile | Branch Setup | Represents operational defaults/configuration for a Branch; internal DocType remains unchanged. |
| RetailEdge Branch Profile User | Do not expose as a standalone destination | Child/internal configuration record. |
| Branch | Branch | Default operating-location term. Use `Operating Branch` only where ambiguity requires explanation. |
| Warehouse | Stock Location / Stock Locations | RetailEdge presentation term where distinction from raw ERPNext Warehouse improves usability. Underlying ERPNext DocType stays `Warehouse`. |
| Warehouse Defaults | Stock Location Defaults | Branch Setup section label. |
| Default Warehouse | Default Stock Location | Internal fieldname remains `default_warehouse`. |
| Default Source Warehouse | Default Source Stock Location | Internal fieldname remains unchanged. |
| Default Target Warehouse | Default Destination Stock Location | Internal fieldname remains unchanged. |
| Default Returns Warehouse | Default Returns Stock Location | Internal fieldname remains unchanged. |
| RetailEdge Cashier Expense | Cashier Expense | Internal DocType remains unchanged. |
| RetailEdge Expense Category | Expense Category / Expense Categories | Internal DocType remains unchanged. |
| RetailEdge Daily Sales Audit | Daily Sales Audit | Internal DocType remains unchanged. |
| RetailEdge Payment Statement Import | Import Bank Statement | Internal DocType remains unchanged. |
| RetailEdge Statement Mapping Template | Bank Statement Mapping | Internal DocType remains unchanged. |
| RetailEdge Bank Transaction Match | Bank Match Review | Internal DocType remains unchanged. |
| RetailEdge Bank Transaction Matching | Bank Matching | Internal report remains unchanged. |
| RetailEdge Customer Receivables | Customer Receivables | Where applicable; internal identity remains unchanged. |
| RetailEdge Supplier Payables | Supplier Payables | Where applicable; internal identity remains unchanged. |
| RetailEdge Planning Scenario | Planning Scenario | Apply when the later planning branch is reconciled. |

## Explicitly retained product branding

`RetailEdge` remains appropriate on true product identity surfaces, including:

- application/product name;
- launcher/product switcher entry;
- login/onboarding/product activation surfaces where product identification is necessary;
- legal/about/support/version information;
- package/internal identifiers;
- cross-product contexts where the product name disambiguates the destination.

The cleanup must not remove RetailEdge branding indiscriminately.

## Implementation requirements

### EdgeSuite primary shell

Audit and normalize all labels/descriptions in the canonical RetailEdge navigation registry and customer-facing EdgeSuite components.

At minimum inspect:

- `retailedge/edgesuite_ui.py`
- `retailedge/public/js/retailedge_business_hub/**`
- `retailedge/public/js/retailedge_product_menu.bundle.js`
- page/dashboard/report Vue components and page definitions that introduce their own visible titles

Do not change target identities merely to change labels.

### Native RetailEdge fallback workspace

Keep the native Workspace as a clean fallback consistent with the EdgeSuite shell.

At minimum inspect:

- `retailedge/workspace_home.py`
- `retailedge/workspace_sync.py`
- committed Workspace JSON
- committed Workspace Sidebar JSON

Generated navigation must remain reproducible after workspace sync/migrate.

### DocType forms and user labels

This phase explicitly includes **field-level and form-level customer-facing labels**, not only navigation.

Audit RetailEdge-owned DocTypes and form customizations for:

- field labels;
- section labels;
- table labels;
- descriptions/help text;
- button labels;
- status/action wording;
- any customer-visible `RetailEdge ...` prefix that adds no useful meaning.

Examples:

- `RetailEdge Branch Profile` remains the internal DocType, while its customer-facing destination is `Branch Setup`.
- `Warehouse Defaults` becomes `Stock Location Defaults` in Branch Setup.
- `Default Warehouse` becomes `Default Stock Location` while the fieldname stays `default_warehouse` and Link options stay `Warehouse`.
- `Default Target Warehouse` becomes `Default Destination Stock Location` while the fieldname stays unchanged.

Do not rename fieldnames, child DocTypes, Link targets, database columns, or internal references in this phase.

### Branch Setup

Preserve internal DocType `RetailEdge Branch Profile` but improve its customer-facing field/section wording where useful.

Use business terminology such as:

- Branch Setup
- POS Defaults
- Stock Location Defaults
- Default Stock Location
- Default Source Stock Location
- Default Destination Stock Location
- Default Returns Stock Location
- Accounting Defaults

Do not change fieldnames or Link options in this phase.

### Reports and pages

Audit titles, headings, empty states, helper text, tooltips, filters, columns, buttons and descriptions. Internal report/page names can remain unchanged when required by Frappe.

### Messages and dialogs

Remove unnecessary customer-visible `RetailEdge` prefixes where they read like technical implementation details. Preserve the name where it genuinely identifies the product or another product/app must be distinguished.

## Safety rules

- Do not rename internal DocTypes.
- Do not rename fieldnames or database columns.
- Do not rename child-table DocTypes.
- Do not rename database tables.
- Do not rename module/package identities.
- Do not rename stable routes solely for presentation cleanup.
- Do not change API method names solely for presentation cleanup.
- Do not change roles in this phase.
- Do not change document permissions.
- Do not mutate submitted accounting or stock documents.
- Do not alter accounting logic, stock logic, branch attribution, pricing, payment, reconciliation, or POS transaction logic.
- Do not introduce broad global CSS/JS overrides to fake labels in the DOM.
- Do not monkey-patch Frappe translation or routing globally.
- Preserve optional POSNext/CoreEdge/EdgePay behavior and standalone RetailEdge operation.

## Required tests

Add focused regression coverage that proves:

1. Canonical customer-facing navigation labels do not unnecessarily expose `RetailEdge` prefixes.
2. Customer-facing DocType field/section labels follow the terminology contract where RetailEdge owns the metadata.
3. Internal targets remain byte-for-byte/stably named where expected.
4. `RetailEdge Branch Profile` still exists as the internal DocType while the visible navigation label is `Branch Setup`.
5. ERPNext `Warehouse` remains the Link/DocType target while RetailEdge-facing labels can say `Stock Location(s)`.
6. Branch Setup fieldnames such as `default_warehouse` and `default_target_warehouse` remain unchanged while their labels are customer-friendly.
7. Child/internal `RetailEdge Branch Profile User` is not exposed as a standalone customer navigation destination.
8. Workspace generator and committed workspace/sidebar fixtures remain aligned.
9. Product identity surfaces that should retain `RetailEdge` continue to do so.
10. No permission, accounting, stock, payment, reconciliation or transactional write behavior is introduced by the terminology phase.

## Mandatory post-implementation audit before phase closure

The first implementation is an audit candidate, not a completed phase.

Audit the implemented phase for:

- missed customer-facing `RetailEdge ...` names;
- missed field/section/dialog/report labels;
- inconsistent terminology across EdgeSuite, native fallback and forms;
- misleading use of Branch versus Stock Location/Warehouse;
- user-unfriendly or unprofessional wording;
- duplicated navigation;
- broken links after label cleanup;
- permission/security regressions;
- company/branch isolation regressions;
- global CSS/JS leakage;
- multi-app coexistence issues;
- migration/workspace-sync drift;
- mobile/responsive presentation issues;
- accidental internal identifier/fieldname renames.

Fix all material findings and rerun exact-head validation before the phase can be marked complete.

## Phase completion summary contract

When Phase 1 is complete, report:

- files changed/created;
- customer-facing labels changed, including field/form labels;
- internal identities explicitly preserved;
- audit findings and fixes;
- tests/CI run and result;
- manual/browser QA status;
- remaining risks/deferred items;
- branch/PR status and promotion recommendation;
- next implementation: **Phase 2 — Operating Branch Switcher**.
