# RIR2 F3F17 — Purchase Return / Supplier Debit Note EdgeSuite Ownership

## Goal

Close the remaining Professional Purchasing ownership gap for Purchase Return and Supplier Debit Note without weakening ERPNext stock or accounting truth.

Ordinary EdgeSuite users must be able to review and submit a standard Purchase Receipt return or supplier Debit Note without being routed into ERPNext Desk. ERPNext remains authoritative for return mapping, validation, stock posting and accounting posting.

## Context

The current Professional Purchasing page exposes two separate business intents:

- Return Received Goods from a submitted Purchase Receipt.
- Create Supplier Debit Note from a submitted Purchase Invoice.

The existing backend correctly uses ERPNext's canonical `make_purchase_return` and `make_debit_note` mappers, validates the mapped target, and inserts only a draft. The current UI then routes to the native Purchase Receipt / Purchase Invoice form. In EdgeSuite-only mode the route guard can block that native route only after the draft side effect already occurred, leaving an incomplete workflow and potentially orphaned drafts.

The normal `SimplePurchaseInvoiceDialog` is not a suitable debit-note owner: it is designed for positive Purchase Invoice entry and carries normal invoice-entry assumptions. F3F17 therefore uses a dedicated return/debit-note review surface while retaining ERPNext's canonical return mappers.

## Scope

1. Add a dedicated, permission-aware backend preview/submit service for standard Purchase Receipt returns and supplier Debit Notes.
2. Preview must map the canonical ERPNext return in memory only. It must not insert, submit, commit, mutate the source, or write GL / Stock Ledger directly.
3. Add an EdgeSuite review overlay that receives the selected source, shows mapped return lines and blockers, and explicitly confirms submission.
4. Intercept the existing Professional Purchasing return/debit-note action before the legacy Vue handler can create a draft, and open the EdgeSuite overlay instead.
5. Keep the two business intents distinct. Never chain a stock return and supplier Debit Note automatically.
6. Preserve explicit advanced native fallback only for users allowed to use Native Desk. Advanced fallback may continue to use the existing draft-first preparation endpoints.
7. Reconcile the legacy UI contract so it no longer requires ordinary success to route to a native draft.

## Out of Scope

- Incoming Quality Inspection ownership.
- Landed Cost ownership.
- Partial/custom return quantity editing inside EdgeSuite.
- Serial/batch bundle editing inside EdgeSuite.
- Tax/accounting override editing inside EdgeSuite.
- Changing ERPNext return, valuation, Stock Ledger, General Ledger, Purchase Receipt or Purchase Invoice posting semantics.
- Mutating submitted Purchase Receipts or Purchase Invoices.
- Automatic creation of both a Purchase Return and Debit Note from one action.

## Implementation Requirements

### Canonical document semantics

- Purchase Return must be an ERPNext Purchase Receipt with `is_return = 1` and `return_against` equal to the submitted source Purchase Receipt.
- Supplier Debit Note must be an ERPNext Purchase Invoice with `is_return = 1` and `return_against` equal to the submitted source Purchase Invoice.
- The mapped target must preserve source Company and Supplier.
- Return item quantities must be negative and there must be at least one remaining returnable item.
- ERPNext's `make_purchase_return` / `make_debit_note` mappers remain the source of truth.

### Preview

Preview must:

- require read access to the source and create access to the target;
- validate the source is submitted, non-return, permitted, company/branch-safe and within the current operating scope;
- map the target in memory only;
- reuse the existing native-return target validation contract;
- return the source `modified` value for freshness protection;
- expose the mapped Company, Branch, Supplier, `return_against`, item lines and whether Purchase Invoice `update_stock` is enabled;
- expose whether the current user has target submit permission;
- fail closed for standard EdgeSuite submission when advanced stock controls cannot safely be completed in the review surface.

### Standard blockers

Standard EdgeSuite submission must not simplify or bypass ERPNext controls. At minimum, block standard submission when a mapped stock-return line requires Serial Number or Batch handling that cannot be completed in this overlay. The advanced ERPNext path remains available only to Native Desk-capable users.

### Submit

Submit must:

- be POST-only;
- lock the submitted source row before remapping to serialize concurrent return attempts;
- require target create and submit permissions;
- compare `expected_source_modified` from preview with the locked source's current `modified` value and reject stale previews;
- rerun source scope validation and canonical mapping after the lock;
- rerun all standard blockers server-side;
- insert and submit the mapped ERPNext return as the current user;
- never use `ignore_permissions=True`;
- never call `frappe.db.commit()` directly;
- never write GL Entry, Stock Ledger Entry, Payment Entry or Journal Entry directly;
- verify the final document is submitted and return a bounded success payload.

ERPNext document submission remains authoritative for stock and accounting effects.

### EdgeSuite UI

- Existing source Link fields remain permission-aware and backend-filtered.
- Clicking `Prepare Draft Return` or `Prepare Draft Debit Note` in the existing cards must be intercepted before the legacy draft-first Vue handler executes.
- The selected source must be passed into a dedicated EdgeSuite overlay.
- The overlay must show source reference, Company, Branch, Supplier, mapped line quantities, warehouse, control blockers, and whether the debit note updates stock.
- Primary action labels must describe the final business operation (`Submit Purchase Return` / `Submit Supplier Debit Note`), not native form handoff.
- Success closes the overlay, shows a bounded confirmation, and refreshes Professional Purchasing.
- EdgeSuite-only users must not require or receive a native ERPNext route for the standard path.
- Native Desk-capable users may use an explicit `Advanced: Prepare in ERPNext` fallback.

## Safety Rules

- Do not mutate submitted source documents.
- Do not alter ERPNext accounting, valuation or Stock Ledger internals.
- Do not bypass DocType create/submit/read permissions.
- Do not weaken branch scope or restricted-zero fail-closed behavior.
- Do not rely on frontend filtering for branch, permission, freshness or posting correctness.
- Do not persist anything during preview.
- Do not automatically pair Purchase Return with Supplier Debit Note.
- Do not include Incoming Quality Inspection or Landed Cost in this slice.

## Tests Required

### Focused source/contract tests

- Dedicated EdgeSuite overlay and bundle exist.
- Existing Return/Debit Note buttons are intercepted in capture phase before legacy handlers.
- Standard flow does not route to native Purchase Receipt / Purchase Invoice forms.
- Advanced fallback is capability-gated.
- Preview is persistence-free and uses canonical ERPNext mappers.
- Submit locks source, checks `modified`, remaps, requires submit permission, then `insert()` + `submit()`.
- No `ignore_permissions=True`, direct commit, direct GL/Stock Ledger/Payment/Journal document creation.
- Legacy contract no longer requires native-route success while preserving the separate business intents and ERPNext mapper assertions.

### Governed gates

All must pass on the exact implementation head:

1. Theme
2. Linters
3. EdgeSuite UI Candidate Compatibility
4. Clean Frappe v16 CI

## Manual QA Pending After Code Freeze

For full FROZEN state, verify at minimum:

- EdgeSuite-only user can select and preview a permitted submitted Purchase Receipt and submit a standard return without Native Desk.
- EdgeSuite-only user can select and preview a permitted submitted Purchase Invoice and submit a standard Debit Note without Native Desk.
- Source documents remain submitted and unchanged.
- Created return/debit-note links and quantities are correct.
- Stock/accounting effects come only from ERPNext submit.
- Stale source is rejected after preview.
- serial/batch-controlled return is blocked from standard submission and does not create a draft.
- restricted branch persona cannot act outside permitted branch and restricted-zero fails closed.
- Native Desk-capable persona sees and can use the explicit advanced fallback.

## Expected Deliverables

- This contract.
- Dedicated backend preview/submit module.
- Dedicated EdgeSuite review overlay and bundle.
- Professional Purchasing ownership interception/mount wiring.
- Focused contract tests and reconciled legacy UI test.
- Exact-head governed gate evidence.
- Godmode ledger update only after all four automated gates are green.
