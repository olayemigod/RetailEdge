# Phase 1 — Customer-Facing Terminology Cleanup

## Goal

Remove unnecessary `RetailEdge` prefixes and technical/internal wording from customer-facing RetailEdge surfaces while preserving stable Frappe/ERPNext/RetailEdge internal identities, routes, DocTypes, reports, permissions, APIs, migrations, accounting truth, and multi-app coexistence.

This phase is presentation and terminology cleanup only. It must not rename internal DocTypes or mutate business transactions.

## Baseline and branch strategy

- `version-16` remains the authoritative ancestor baseline.
- Current R2 usability foundation is directly ahead of `version-16` and contains the active professional single-shell UX.
- Implement Phase 1 on a dedicated branch from the current R2 foundation.
- Preserve all later stacked branches. Reconcile downstream stacks only after this phase is audited, validated, QA-approved, and promoted.

## Customer-facing naming principles

1. Do not repeat the product name when the user is already inside RetailEdge.
2. Prefer plain business terminology over package/framework terminology.
3. Keep internal package, DocType, report, role, route, module, API, and database identities stable unless a separate migration is explicitly approved.
4. ERPNext remains the underlying system of record. Customer-facing labels may be friendlier, but they must not misrepresent accounting or stock semantics.
5. Customer-facing names should remain understandable when RetailEdge coexists with other ProcessEdge or third-party Frappe apps.
6. The EdgeSuite shell, RetailEdge native fallback workspace, dialogs, pages, dashboards, report titles, descriptions, buttons, setup links, empty states, and user-facing messages should follow the same terminology contract.

## Initial terminology contract

| Internal / current target | Customer-facing label | Notes |
| --- | --- | --- |
| RetailEdge Business Hub | Business Hub | Product context already says RetailEdge. |
| RetailEdge Settings | Settings | Internal DocType stays `RetailEdge Settings`. |
| RetailEdge Branch Profile | Branch Setup | Represents operational defaults/configuration for a Branch; internal DocType remains unchanged. |
| RetailEdge Branch Profile User | Do not expose as a standalone destination | Child/internal configuration record. |
| Branch | Branch | Default operating-location term. Use `Operating Branch` only where ambiguity requires explanation. |
| Warehouse | Stock Location / Stock Locations | RetailEdge navigation/presentation term where a distinction from the raw ERPNext Warehouse master improves usability. Underlying ERPNext DocType remains `Warehouse`. |
| Default Warehouse | Default Stock Location | Branch Setup presentation term. |
| Default Source Warehouse | Default Source Stock Location | Branch Setup presentation term. |
| Default Target Warehouse | Default Destination Stock Location | Branch Setup presentation term. |
| Default Returns Warehouse | Default Returns Stock Location | Branch Setup presentation term. |
| RetailEdge Cashier Expense | Cashier Expense | Internal DocType remains unchanged. |
| RetailEdge Expense Category | Expense Category / Expense Categories | Internal DocType remains unchanged. |
| RetailEdge Daily Sales Audit | Daily Sales Audit | Internal DocType remains unchanged. |
| RetailEdge Payment Statement Import | Import Bank Statement | Internal DocType remains unchanged. |
| RetailEdge Statement Mapping Template | Bank Statement Mapping | Internal DocType remains unchanged. |
| RetailEdge Bank Transaction Match | Bank Match Review | Internal DocType remains unchanged. |
| RetailEdge Bank Transaction Matching | Bank Matching | Internal report remains unchanged. |
| RetailEdge Customer Receivables | Customer Receivables | Where applicable; page/report internal identity remains unchanged. |
| RetailEdge Supplier Payables | Supplier Payables | Where applicable; page/report internal identity remains unchanged. |
| RetailEdge Planning Scenario | Planning Scenario | Apply when later stacked planning branch is reconciled. |

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

Audit titles, headings, empty states, helper text, tooltips, filters, buttons and descriptions. Internal report/page names can remain unchanged when required by Frappe.

### Messages and dialogs

Remove unnecessary customer-visible `RetailEdge` prefixes where they read like technical implementation details. Preserve the name where it genuinely identifies the product or another product/app must be distinguished.

## Safety rules

- Do not rename internal DocTypes.
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
2. Internal targets remain byte-for-byte/stably named where expected.
3. `RetailEdge Branch Profile` still exists as the internal DocType while the visible navigation label is `Branch Setup`.
4. ERPNext `Warehouse` remains the target while the RetailEdge customer-facing navigation label is `Stock Locations`.
5. Child/internal `RetailEdge Branch Profile User` is not exposed as a standalone customer navigation destination.
6. Workspace generator and committed workspace/sidebar fixtures remain aligned.
7. Product identity surfaces that should retain `RetailEdge` continue to do so.
8. No permission, accounting, stock, payment, reconciliation or transactional write behavior is introduced by the terminology phase.

## Mandatory post-implementation audit before phase closure

The first implementation is an audit candidate, not a completed phase.

Audit the implemented phase for:

- missed customer-facing `RetailEdge ...` names;
- inconsistent terminology across EdgeSuite and native fallback surfaces;
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
- accidental internal identifier renames.

Fix all material findings and rerun exact-head validation before the phase can be marked complete.

## Audit-candidate findings and remediations

The first implementation audit has already identified and corrected the following issues:

1. **Ambiguous branch-user wording** — `Preferred User` was not precise enough for the existing `is_default` meaning. It was corrected to **Default for Role**.
2. **Workspace regeneration drift** — workspace sync could have reintroduced `RetailEdge Business Hub`. The workspace sync source now uses **Business Hub** consistently.
3. **Duplicate/unscoped title handlers** — the first shared customer-title helper could register handlers for unrelated RetailEdge forms. It is now scoped to the currently loaded DocType, and Settings/Branch Setup retain their dedicated title scripts.
4. **Implementation-era Settings copy** — user-visible Settings descriptions contained phase/version/internal wording. These were rewritten as durable business controls without changing the underlying fields or behaviour.
5. **Warehouse terminology inconsistency** — RetailEdge-facing navigation and Branch Setup now use **Stock Location(s)** while ERPNext `Warehouse` remains the Link target/system of record.
6. **Cashier Expense internal/future wording** — user-facing help text no longer exposes product-internal wording or unfinished `future/reserved` implementation language. Posting/readiness descriptions remain careful not to claim an accounting entry exists when it has not been posted.
7. **Bank Match Review technical labels** — abbreviations/framework labels such as `SI/PE Amount`, `Technical`, and `Execution Candidate DocType` were replaced with clearer business-facing labels such as **Candidate Amount**, **System Details**, and **Execution Candidate Type**.
8. **Static metadata audit coverage** — focused tests now scan RetailEdge-owned DocType field labels/descriptions for unnecessary `RetailEdge` prefixes so missed customer-facing metadata fails validation rather than relying on manual spot checks.

The phase remains **open / audit candidate** until exact-head CI, broader page/dialog/report audit, manual browser QA, and final security/permission/coexistence review pass.

## Phase completion summary contract

When Phase 1 is complete, report:

- files changed/created;
- customer-facing labels changed;
- internal identities explicitly preserved;
- audit findings and fixes;
- tests/CI run and result;
- manual/browser QA status;
- remaining risks/deferred items;
- branch/PR status and promotion recommendation;
- next implementation: **Phase 2 — Operating Branch Switcher**.
