# Phase 3 — Branch Defaults & Operational Context Activation

## Goal

Activate the Phase 2 Operating Company / Operating Branch context safely across new RetailEdge transaction work, branch defaults, POS Profile resolution, and selected operational reports without changing historical document truth.

## Scope Implemented

### 3A — New-document Operating Context seeding

- Only genuinely new, draft documents are eligible.
- Existing drafts already stored in the database are not re-contextualized.
- Submitted and cancelled documents are never changed.
- Explicit branch-driving evidence wins over Operating Context, including Branch, RetailEdge Branch attribution, POS Profile, linked POS opening/closing state, and Stock Location fields.
- Operating Context may seed missing Company and Branch attribution only.
- Existing Branch Setup defaults remain the source for Stock Location, Cost Center, account and POS Profile defaults.

### 3B — Shared full-form defaults application

- `retailedge.new_document_defaults.get_new_document_operating_defaults` previews defaults against an unsaved in-memory document.
- The endpoint requires create permission for the target DocType.
- The preview never inserts, saves, submits, cancels, commits or writes database state.
- Server-side validation rejects forged Company, Branch, Stock Location, POS Profile and linked POS-context values that are not readable or do not belong to the selected Company/Branch.
- One shared Desk helper applies only missing scalar values to supported new ERPNext transaction forms.
- Child-row arrays are intentionally not copied from the preview response.
- User-entered values are never overwritten by the client helper.
- Company changes clear and re-resolve only RetailEdge-owned dependent defaults.
- Branch changes clear and re-resolve only RetailEdge-owned Branch-dependent defaults.
- Stale asynchronous responses are discarded using a generation counter.

### 3C — POS Profile/default propagation

- Branch Setup POS Profile defaults are applied only to `POS Invoice` and POS-mode `Sales Invoice`.
- Ordinary Sales Invoice, Sales Order and Delivery Note do not receive a POS Profile merely because a Branch Setup has one.
- POS Profile existence, read permission, disabled state, Company compatibility and Branch compatibility are validated server-side.
- Invalid Branch Setup POS Profile defaults are skipped rather than blocking accounting/stock document validation.
- Explicit POS Profile selections remain authoritative.
- Changing `Sales Invoice.is_pos` re-resolves only RetailEdge-owned POS Profile defaults.

### 3D — Operating defaults for operational reports

Operating Company/Branch now supplies initial editable defaults for:

- Sales by Item
- Sales Invoice Register
- Purchase Register
- Supplier Payables
- Stock Position

The existing report engines/providers remain authoritative for data retrieval, permissions, pagination, export and cost visibility.

## Dedicated Audit Findings

### High — Branch-restricted users could broaden report scope

**Finding**

The existing report engines enforce `get_user_allowed_branches`, but Branch Setup membership was not part of that legacy helper. A user assigned to one Branch Setup could clear the report Branch filter and, where no separate Branch User Permission existed, potentially fall back to a broader ERPNext read scope.

**Remediation**

Phase 3 wraps the Sales, Purchase and Stock Position context/search/data/export endpoints:

- global branch-access roles retain intentional cross-branch reporting;
- users with active Branch Setup assignments must report within an assigned Branch;
- Branch search options are restricted to assigned Branches;
- a Branch outside the assignment is rejected server-side;
- clearing Branch and requesting cross-branch data is rejected for Branch-restricted users;
- sites/users with no Branch Setup assignments retain existing ERPNext/User Permission behavior;
- configured-but-disabled assignment state fails closed;
- assignment lookup errors fail closed.

### High — New-form preview accepted untrusted context values too early

**Finding**

Create permission on the target DocType alone did not prove that forged Company, Branch, Stock Location, POS Profile or POS shift values supplied to the preview endpoint were valid for the current user and business context.

**Remediation**

The preview API now validates server-side:

- Company existence/read access;
- Branch existence/read/access and Company relationship;
- Stock Location existence/read access and Company/Branch relationship;
- POS Profile existence/read access and Company/Branch relationship;
- linked POS opening/closing document read access and Company/Branch relationship.

### Medium — Branch changes could leave old Branch defaults on a new form

**Finding**

Company changes were re-resolved, but Branch changes initially were not. RetailEdge-owned Stock Location, Cost Center or POS Profile values from the old Branch could therefore remain populated and prevent safe re-resolution.

**Remediation**

The client helper tracks values it auto-applied. On Branch change it clears only fields that still equal those prior RetailEdge-owned defaults, preserves any user-edited value, then requests a fresh server preview. Equivalent narrow handling applies to `Sales Invoice.is_pos` changes for POS Profile.

## Safety Invariants

- No mutation of submitted accounting or stock documents.
- No new GL Entry or Stock Ledger posting logic.
- No save/submit/cancel/commit side effects in preview/default-resolution paths.
- No `ignore_permissions`.
- Company remains the accounting boundary.
- ERPNext Warehouse remains the stock system of record; RetailEdge presents it as Stock Location in customer-facing UI.
- Existing Branch Setup/default resolver behavior remains the source of operational defaults.
- Existing report providers and permission checks remain in use; Phase 3 adds a Branch Setup access constraint where configured.
- No global DOM, CSS, route or translation monkey patch is introduced.
- POSNext/CoreEdge remain optional integration providers; Phase 3 does not add mandatory imports from them.

## Automated Validation

Regression coverage includes:

- new-document-only seeding;
- explicit-context precedence;
- existing/submitted document protection;
- preview create permission and no-write guarantee;
- forged context validation;
- shared full-form client registration;
- scalar-only application and user-edit preservation;
- stale-response protection;
- Company and Branch cascade re-resolution;
- Sales Invoice POS-mode re-resolution;
- POS Profile applicability/validation;
- report context/search/data/export wrapper coverage;
- Branch Setup report restriction and fail-closed behavior;
- editable/clearable report Branch controls;
- stock cost-visibility preservation;
- absence of accounting/stock posting side effects.

## Manual / Browser QA Required Before Promotion

Because Phase 3 is stacked on the Phase 2 Operating Branch Switcher, final browser QA remains predecessor-gated. Validate at minimum:

1. New Sales Order, Delivery Note, Sales Invoice and POS Invoice defaults.
2. New Purchase Order, Purchase Receipt and Purchase Invoice defaults.
3. New Material Request and Stock Entry defaults.
4. Company change on an unsaved form.
5. Branch change on an unsaved form.
6. User-edited Stock Location/Cost Center values survive context changes where they are no longer RetailEdge-owned.
7. `Sales Invoice.is_pos` off/on POS Profile behavior.
8. Invalid/mismatched Branch Setup POS Profile is not silently applied.
9. Sales/Purchase/Stock report initial Operating Branch defaults.
10. Restricted user cannot broaden outside Branch Setup assignment.
11. Global branch manager can clear Branch and use authorized cross-branch scope.
12. Report Branch/Stock Location search remains permission-aware and company/branch filtered.
13. Existing drafts do not get re-contextualized when opened.
14. Submitted/cancelled documents remain unchanged.
15. POSNext/multi-app Desk loading shows no shared-shell regression.

## Promotion Rule

Phase 3 is not complete merely because implementation exists. Promotion requires:

1. dedicated audit findings remediated;
2. exact-head Linters and clean Frappe v16 CI green;
3. Phase 2 predecessor browser QA no longer blocking;
4. Phase 3 browser/manual QA completed against the exact implementation head;
5. PR documentation updated with final exact SHA, test runs, remaining risks and promotion decision.
