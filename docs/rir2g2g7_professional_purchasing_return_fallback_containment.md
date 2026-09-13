# RIR2G2G7 — Professional Purchasing Legacy Return Fallback Containment

## Goal

Preserve the EdgeSuite-owned Purchase Return / Supplier Debit Note review workflow while preventing the legacy native fallback handlers from opening ERPNext for EdgeSuite-only users.

## Ownership finding

The visible Returns & Supplier Credits controls are not an unfinished native-only workflow.

`professionalPurchaseReturnOwnership.js` captures the normal buttons before their legacy Vue handlers, stops propagation, and opens `ProfessionalPurchaseReturnReviewOverlay.vue`.

The overlay owns the standard EdgeSuite path:
- review ERPNext's mapped return/debit-note result inside RetailEdge;
- submit through the configured ERPNext Workflow where applicable;
- otherwise perform the governed standard submission path;
- expose `Advanced: Prepare in ERPNext` only when Native Desk fallback is enabled.

Therefore Phase 3 must **not** hide or remove the ordinary Returns & Supplier Credits section.

## Current gap

The legacy fallback methods in `ProfessionalPurchasing.vue`:
- `preparePurchaseReturn()`
- `prepareSupplierDebitNote()`

still call the draft-first ERPNext mapper and route to native Forms if invoked directly/programmatically, even when Native Desk is disabled.

## Required contract

- Keep the Returns & Supplier Credits EdgeSuite controls visible according to their existing operational capabilities.
- Keep the capture-phase ownership bridge and EdgeSuite review overlay unchanged.
- Add `canUseNativeDesk` fail-closed guards to both legacy native fallback methods.
- Preserve the overlay's separately gated `Advanced: Prepare in ERPNext` behavior for authorised Native Desk users.
- Do not change return/debit-note mapping, workflow, stock, accounting or submission semantics.

## Safety rules

- No backend mapper or return calculation changes.
- No mutation of submitted Purchase Receipt / Purchase Invoice sources.
- No Branch, Company or permission changes.
- No Workflow semantic changes.
- No shared EdgeSuite UI runtime changes.
- No removal of the standard EdgeSuite return/debit-note workflow.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- legacy Purchase Return fallback method checks `canUseNativeDesk`;
- legacy Supplier Debit Note fallback method checks `canUseNativeDesk`;
- capture-phase ownership with `stopImmediatePropagation()` remains;
- EdgeSuite review/submit APIs remain;
- Advanced ERPNext action remains separately Native-Desk-gated.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
