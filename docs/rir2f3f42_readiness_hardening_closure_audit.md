# RIR2F3F42 — Readiness Hardening Closure Audit

## Goal

Close the remaining code-level Readiness Hardening composition defects before Phase 1 is declared code-complete. This slice must not create new accounting, stock, reporting or master-data engines.

## Audit Baseline

The authoritative reconciled line already contains governed fixes for:

- authoritative branch composition and restricted-zero Branch scope;
- EdgeSuite Desk Access presentation without changing ERPNext permissions;
- guided Stock Transfer server-side Branch/Warehouse enforcement;
- EdgeSuite-only operational route containment;
- standard Selling, Purchasing, Payment, Expense, Quality Inspection and Landed Cost ownership;
- shared Frappe Workflow precedence through F3F27;
- ERPNext lifecycle authority for accounting/stock posting.

Two bounded code-level defects remain.

## Blocker A — Stock Movement History composition

### Evidence

- A hardened EdgeSuite Page `stock-movement-history` already exists.
- Its page API and export reuse the same bounded stock-ledger dataset authority.
- Operational Branch/Company/Warehouse scope and restricted-zero behavior are already hardened.
- The page uses shared EdgeSuite export and canonical EdgeSuite runtime.
- The legacy Query Report remains valuable as a Native Desk compatibility/reference fallback.
- Final Business Hub composition still deliberately leaves **Stock Movement History** pointing to `RetailEdge Stock Movement History` Query Report because an older parity/browser hold predates the later page hardening.

### Closure decision

When the current user may open the EdgeSuite Page and the existing permitted navigation contains the legacy Stock Movement History report item:

- final RetailEdge composition must replace that item with Page `stock-movement-history`;
- the legacy Query Report remains installed and directly available to authorised Native Desk users;
- no stock calculation, filter semantics, export semantics, opening balance, running balance or source ledger logic changes;
- browser/persona acceptance remains deferred to RIR2E, so this slice is code-frozen/QA-pending rather than release-frozen.

If the Page is unavailable or not permitted, the existing permission-safe legacy navigation remains unchanged for compatible Native Desk users.

## Blocker B — Business Hub master quick actions

### Evidence

Final Business Hub context may append permission-approved:

- New Customer;
- New Supplier;
- New Product.

The current Business Hub Vue handler does not own those keys. It falls through to the native fallback gate, so an EdgeSuite-only user can be shown an action that then reports that native Desk is unavailable.

Existing guided invoice dialogs already use Frappe Quick Entry for Customer/Supplier/Item creation without routing the user into a native Desk Form/List.

### Closure decision

Reuse that established Quick Entry helper for the three fixed master actions:

- New Customer → Customer Quick Entry;
- New Supplier → Supplier Quick Entry;
- New Product → Item Quick Entry.

Requirements:

- only server-advertised actions already gated by create permission are exposed;
- frontend maps fixed action keys to fixed DocTypes and never trusts a browser-supplied arbitrary DocType for this path;
- Quick Entry remains subject to normal Frappe/ERPNext permissions and validation;
- no `ignore_permissions`, direct database write, custom master ledger or custom DocType is introduced;
- success stays in Business Hub and does not route EdgeSuite-only users into native Desk;
- cancellation is a no-op;
- native Desk capability is not required for these three Quick Entry actions.

## Closure Matrix

| Area | Classification after F3F42 | Evidence / boundary |
| --- | --- | --- |
| Authoritative PR/branch line | EDGESUITE_OWNED / HARDENED | PR #55 reconciled branch and governed exact-head gates |
| Role Desk access | HARDENED | Roles remain System User-capable; shared access context controls interface exposure only |
| Operational Branch scope | HARDENED | Restricted/single/multi/zero contracts are server-side |
| Guided Stock Transfer | HARDENED WITH INTENTIONAL NATIVE DRAFT LIFECYCLE | Branch/Warehouse validated server-side; Stock Entry remains draft-only by frozen baseline |
| Professional Selling | EDGESUITE_OWNED | F3F1+ containment/ownership slices |
| Professional Purchasing | EDGESUITE_OWNED STANDARD PATH | F3F16–F3F41; advanced exceptional cases remain native |
| Payment Management | EDGESUITE_OWNED STANDARD PATH | F3F4–F3F8; reconciliation/payment-order treasury cases remain advanced |
| Expenses | EDGESUITE_OWNED STANDARD PATH | F3F25–F3F34 |
| Incoming Quality Inspection | EDGESUITE_OWNED STANDARD PATH | F3F40 |
| Landed Cost | EDGESUITE_OWNED STANDARD PATH | F3F41 |
| Stock Movement History | READINESS_BLOCKER → EDGESUITE_OWNED | promote existing hardened Page; retain legacy report fallback |
| Customer/Supplier/Product creation from Business Hub | READINESS_BLOCKER → EDGESUITE-HOSTED QUICK ENTRY | reuse existing Frappe Quick Entry helper under normal permissions |
| Native detailed accounting reports | INTENTIONAL_ADVANCED_NATIVE / REPORTING-PHASE INPUT | GL/TB/P&L/BS etc. are not rebuilt in Phase 1 |
| Payment Reconciliation / Payment Orders / treasury controls | INTENTIONAL_ADVANCED_NATIVE | already explicitly classified by F3F7/F3F8 |
| Stock Entry advanced completion / serial-batch complex cases | INTENTIONAL_ADVANCED_NATIVE | frozen product baseline; no new posting engine |
| Setup/master administration not already EdgeSuite-owned | INTENTIONAL_ADVANCED_NATIVE | administrative configuration, not an everyday Phase 1 ownership blocker |
| Business Hub release acceptance | CONSOLIDATED_QA_PENDING | implementation exists; browser/persona/release QA is later |

## Scope

Runtime:
- `retailedge/master_experience.py`
- `retailedge/public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue`
- `retailedge/public/js/retailedge_business_hub/guidedEntryUtils.js` only if needed to expose a reusable blank Quick Entry helper.

Tests:
- new F3F42 closure contract tests;
- reconcile stale Stock Movement History hold tests/docs only where this slice supersedes them.

Documentation:
- this contract;
- stale pre-reporting operational-surface wording;
- Godmode state ledger after exact-head gates pass.

## Out of Scope

- changing submitted accounting or stock documents;
- Stock Entry submit ownership;
- Stock Reconciliation submit ownership;
- serial/batch advanced stock workflows;
- rebuilding ERPNext detailed financial reports;
- replacing Payment Reconciliation or Payment Order;
- building Customer/Supplier/Item management pages;
- pricing/setup/master administration redesign;
- reporting expansion;
- Business Hub feature expansion beyond the two closure defects;
- manual browser/persona QA before RIR2E;
- merge/release/final MVP freeze.

## Safety Rules

- ERPNext remains system of record.
- Do not broaden Frappe Page, Report or DocType permissions.
- Do not convert restricted-zero into unrestricted access.
- Do not use `ignore_permissions` or manual database commit.
- Do not mutate submitted documents.
- Do not remove the legacy Stock Movement History Query Report from ERPNext.
- Do not promote the EdgeSuite Stock Movement History Page when it is unavailable/not permitted.
- Do not trust arbitrary frontend DocType names for master Quick Entry.
- Do not turn deliberate advanced-native routes into fake EdgeSuite ownership.

## Tests Required

1. Stock Movement History promotion occurs only when its Page is permission-available.
2. Promotion changes only the existing Stock Movement History navigation item to Page `stock-movement-history`.
3. If Page permission is unavailable, the legacy Query Report item is preserved.
4. Legacy Query Report files remain installed.
5. Page/export/bounded dataset and branch-scope contracts remain unchanged.
6. Business Hub recognizes New Customer/New Supplier/New Product explicitly.
7. Each master action maps to a fixed DocType and uses the reusable Quick Entry helper.
8. Master Quick Entry does not require `nativeFallbackEnabled`.
9. Unknown/non-guided actions still fail closed when Native Desk is unavailable.
10. No arbitrary action.doctype is passed to the master Quick Entry helper.
11. No backend accounting/stock/module schema file is changed by the slice.
12. Existing restricted-zero, access-hardening and operational-guard tests remain green.

## Phase Closure Rule

If these two blockers are fixed and all four governed exact-head gates pass, Phase 1 may be recorded as:

**READINESS HARDENING — CODE-COMPLETE / CONSOLIDATED QA-PENDING**

This does not claim browser/persona acceptance, release readiness, reporting completion, or MVP freeze.
