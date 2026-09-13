# E16 Supplier Document → Draft Purchase Invoice Handoff

## Business goal

Close the supplier-document workflow gap without creating a shadow buying or accounting path.

A private Supplier Invoice uploaded against a submitted ERPNext Purchase Order can now move through:

1. internal source-document review;
2. immutable manual/provider-neutral extraction evidence;
3. immutable extraction acceptance/rejection;
4. final source-document acceptance;
5. explicit human action to prepare an ERPNext **draft** Purchase Invoice.

## Accounting and purchasing authority

ERPNext remains authoritative.

- The authoritative Supplier, Company and Purchase Order come from Supplier Document Intake and are revalidated server-side.
- The Purchase Invoice is created with ERPNext v16's Purchase Order → Purchase Invoice mapper.
- PO mapping owns items, remaining quantities, rates, taxes and Purchase Order linkage.
- Extracted totals, tax and subtotal remain advisory evidence and are not written into the mapped accounting document.
- Extracted supplier document number and date may populate the draft's supplier bill reference after acceptance.
- A currency mismatch between extraction evidence and the ERPNext-mapped draft fails closed.
- The handoff creates a draft only. It never submits a Purchase Invoice or creates Payment Entry, GL Entry or Stock Ledger Entry.

## Audit and duplicate prevention

`Supplier Document Purchase Invoice Handoff` is an immutable internal audit record.

- one extraction can have only one handoff;
- the accepted extraction review, intake, private source File, Purchase Order and resulting Purchase Invoice are retained;
- repeat requests are idempotent and return the existing Purchase Invoice when it still exists;
- if the handed-off draft is deliberately deleted, the immutable handoff is not rewritten or deleted; staff must record a new extraction before another handoff.

## EdgeSuite UI

All new operational frontend is the `supplier-document-review` EdgeSuite page.

- it requires `window.EdgeSuiteUI` and mounts through `createEdgeApp`;
- it uses `EdgeAppShell` and `EdgeLinkField`;
- no legacy `window.EdgeUI` fallback is present;
- no native `frappe.ui.Dialog` is used for this workflow;
- Company → Branch and Supplier filtering is permission-aware and server validated;
- the page exposes the staged review actions and links to authoritative ERPNext Purchase Orders and Purchase Invoice drafts.

## Deployment

Normal `bench migrate` is required because the slice adds one standard DocType and one standard Page. Assets must be rebuilt for the new EdgeSuite bundle.

## Manual QA later

Manual QA remains deferred to the consolidated QA line. When enabled, verify role visibility, Company/Branch isolation, private-file access, extraction/review sequencing, rejection-note handling, accepted-only draft preparation, PO remaining-quantity mapping, supplier bill number/date carry-over, currency mismatch fail-closed behaviour, repeated handoff idempotency, no submit/Payment/GL/SLE side effects, and light/dark/mobile EdgeSuite presentation.
