# RIR2 F3F12 — Cash Shift Native Detail Containment

## Goal

Close the remaining ordinary-user escape from the EdgeSuite Cash Shift Verification report into native ERPNext/Frappe Desk forms without changing cash-shift calculations, branch scope, Daily Sales Audit truth, POS posting semantics, or ERPNext permissions.

## Evidence

The current `CashShiftVerificationReport.vue` already loads the permission-filtered RetailEdge Business Hub navigation context, but its report cells independently route directly to native forms for:

- RetailEdge Daily Sales Audit;
- User;
- POS Profile;
- POS Opening Shift;
- POS Closing Shift.

Those row-level handoffs are outside the filtered navigation menu and therefore must independently honor the final EdgeSuite access context.

## Contract

For a user whose final EdgeSuite access context has `can_use_native_desk = false`:

- Cash Shift Verification remains readable in EdgeSuite;
- native-detail columns are not presented as clickable;
- row-cell events cannot open native Desk forms;
- DocType/Report navigation handoffs are defensively blocked even if an unexpected item reaches the client.

For a user whose final access context has `can_use_native_desk = true`, the existing native-detail handoffs remain available subject to the existing server-side document/report permissions.

The component must fail closed before the access context resolves.

## Out of Scope

This slice does not:

- redesign Cash Shift Verification;
- add an EdgeSuite editor for Daily Sales Audit, User, POS Profile, POS Opening Shift, or POS Closing Shift;
- change branch authorization or report filtering;
- change POS, accounting, GL, Stock Ledger, valuation, submission, cancellation, or document lifecycle semantics;
- weaken Frappe/ERPNext permission checks;
- address unrelated native handoffs in other EdgeSuite reports or operational pages.

Those surfaces must be audited and handled as separate bounded slices where evidence identifies a gap.

## Required Evidence

- focused static contract test for fail-closed access initialization and guarded row/menu handoffs;
- full RetailEdge governed gates on the exact implementation head;
- authenticated browser/persona QA for Native Desk allowed and denied users before the slice is represented as fully frozen.

Until browser/persona evidence exists, the maximum state is `CODE-FROZEN / QA-PENDING`.
