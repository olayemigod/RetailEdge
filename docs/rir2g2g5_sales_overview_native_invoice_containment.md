# RIR2G2G5 — Sales Overview Native Invoice Containment

## Goal

Keep Sales Overview usable for EdgeSuite-only users while preventing the dashboard from exposing native Sales Invoice Forms or stale/tampered Report/DocType navigation.

## Current gap

Sales Overview is EdgeSuite-owned and already links its operational drill-down buttons to EdgeSuite Pages. However:

- every Recent Invoice row is a button that opens the native Sales Invoice Form;
- `openInvoice()` has no Native Desk capability guard;
- shell `handleNavigation()` can route Report/DocType targets if stale or tampered navigation reaches the page;
- the page loads the shared navigation context but does not retain `access.can_use_native_desk`.

## Required contract

- Native Desk defaults closed.
- Read capability from shared `navigation.access.can_use_native_desk`.
- Recent invoice number, customer, date and total remain visible for all users.
- Recent invoice rows are native Form actions only when Native Desk is allowed.
- EdgeSuite-only users receive static invoice rows.
- `openInvoice()` fails closed when Native Desk is unavailable.
- shell navigation fails closed before Report/DocType routing when Native Desk is unavailable.
- Existing EdgeSuite routes to Sales Invoice Register, Sales by Item, Salesperson Performance and Branch Performance remain available.

## Safety rules

- No Sales Invoice mutation.
- No sales/report calculations, filters, summaries, export or print behavior changes.
- No ERPNext role/permission/desk-access change.
- No accounting or stock semantics change.
- No shared EdgeSuite UI runtime change.
- Do not replace the native invoice Form in this slice.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- Native fallback defaults false and is sourced from shared access context.
- Recent invoice identity remains visible in both native-capable and EdgeSuite-only presentation.
- EdgeSuite-only Recent Invoice rows are static.
- `openInvoice()` fails closed without Native Desk.
- Report/DocType shell navigation fails closed without Native Desk.
- existing EdgeSuite drill-down routes remain unchanged.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
