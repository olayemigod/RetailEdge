# RIR2F2E2 — RFQ EdgeSuite History Ownership

## Goal

Close the RFQ read-side ownership gap after RIR2F2E1.

Before this slice, the Professional Purchasing hero still exposed `RFQs` as a native ERPNext list action. EdgeSuite-only users could not use that route because the shared operational guard correctly blocks native Request for Quotation list/form access.

RIR2F2E2 makes RFQ history a normal RetailEdge read experience without changing RFQ submission, supplier communication or Supplier Quotation workflows.

## Frozen parent

RIR2F2E1 Sourcing / RFQ Preview Ownership:

`1bff30b6e975a009fe25d4eea1dc61b3cd264f04`

## Runtime ownership

The existing Professional Purchasing `RFQs` button is promoted to:

`RFQ History`

The button is capture-intercepted before the legacy Vue native-list handler can run.

Normal users remain inside EdgeSuite.

## History backend

`retailedge.professional_sourcing.get_request_for_quotation_history` provides the read model.

The endpoint:

- requires Request for Quotation read permission;
- resolves the active Company and Branch using the Professional Purchasing operating-context contract;
- applies `_branch_scoped_filters()` so restricted branch users cannot broaden the read;
- supports Supplier filtering;
- uses permission-aware `frappe.get_list()` for parent RFQs;
- caps output at 100 rows server-side;
- enriches only the already permission-scoped parent names with Supplier and item-count child-table information;
- returns draft, submitted and cancelled RFQs that match the permitted scope.

Supplier filtering may use the RFQ Supplier child table to derive candidate parent names, but the returned parent documents are still resolved through the permission-aware Request for Quotation `get_list()` query.

## EdgeSuite history overlay

The RFQ History overlay supports:

- Company filter;
- Branch filter;
- Supplier filter;
- cascading Company changes that clear Branch and Supplier;
- sortable RFQ number, date, item-count and status columns;
- Supplier visibility per RFQ;
- bounded result visibility.

RFQ identifiers are plain references, not disguised native links.

## Native Desk fallback

Native ERPNext access remains secondary and explicit.

Only users whose shared EdgeSuite access mode allows Native Desk see:

- `Advanced: Open in ERPNext`
- `Advanced: RFQs in ERPNext`

EdgeSuite-only users are not shown those actions.

The shared operational guard remains unchanged and continues to block direct native Request for Quotation form/list routes for EdgeSuite-only users.

## Out of scope

RIR2F2E2 does not:

- submit RFQs;
- send Supplier email;
- edit RFQ terms or supplier contacts;
- implement Supplier Quotation history or entry;
- implement quotation comparison inside EdgeSuite;
- alter Purchase Order, Purchase Receipt, Purchase Invoice or accounting behavior;
- weaken ERPNext permissions or branch scope.

## Next bounded sourcing gaps

After this slice is frozen, the remaining ordinary sourcing gaps should be audited separately:

1. standard RFQ review/submission;
2. Supplier Quotation read/history ownership;
3. Supplier Quotation capture where required for ordinary users;
4. quotation comparison ownership.

Advanced communication, unusual terms and exceptional procurement cases may remain native where parity is intentionally not claimed.

## Required validation

Freeze only when the exact SHA passes:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 standalone CI and full RetailEdge test suite;
- governed EdgeSuite UI candidate compatibility.

Manual browser/persona QA remains separate and must not be claimed from automated gates.
