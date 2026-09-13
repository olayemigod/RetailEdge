# RIR2F2E3 — Standard RFQ Submit

## Goal

Close the standard sourcing completion gap for an EdgeSuite-only buyer after RFQ preview and RFQ history became EdgeSuite-owned.

RIR2F2E3 allows a standard Request for Quotation to be created and submitted from the RetailEdge RFQ preview while preserving ERPNext as the source of truth for RFQ validation and submission.

Supplier communication remains deliberately disabled in this slice.

## Frozen parent

RIR2F2E2 RFQ History Ownership:

`7904be35a71df2744d01834575e0f7d0c9e47e13`

## ERPNext v16 submission behavior verified

The ERPNext v16 `Request for Quotation` controller was inspected before implementing this slice.

On submit, ERPNext:

1. sets RFQ status to Submitted;
2. marks each Supplier response status Pending;
3. calls its Supplier-send routine;
4. actually sends only for Supplier rows whose `send_email` flag is enabled and where an email address exists.

RetailEdge therefore uses normal ERPNext `insert()` and `submit()`, but appends every selected Supplier with:

`send_email = 0`

This allows the RFQ document to reach submitted ERPNext state without issuing Supplier email or creating a supplier-portal communication flow behind the user's back.

## Standard submit endpoint

`retailedge.professional_sourcing.submit_standard_request_for_quotation`

The endpoint is POST-only.

It performs the following sequence:

1. validates the Material Request name and read permission;
2. locks the Material Request database row with `FOR UPDATE`;
3. reloads and validates the submitted Purchase Material Request;
4. requires Request for Quotation create permission;
5. requires Request for Quotation submit permission;
6. validates every selected Supplier;
7. compares the Material Request `modified` value against the preview token and rejects stale previews;
8. revalidates Company/Branch scope, including fail-closed behavior for restricted blank-Branch source documents;
9. detects an existing non-cancelled RFQ for the same Material Request and exact Supplier set;
10. freshly maps the RFQ using ERPNext `make_request_for_quotation()`;
11. appends Suppliers with `send_email = 0`;
12. calls normal ERPNext `rfq.insert()` and `rfq.submit()` as the current user;
13. verifies submitted `docstatus` before returning success.

## Retry / duplicate safety

A Material Request row lock prevents concurrent standard-submit requests from passing duplicate checks simultaneously.

The duplicate guard looks for active RFQs linked through `Request for Quotation Item` to the same Material Request and compares the Supplier set from `Request for Quotation Supplier`.

If an active RFQ already has the exact same Supplier set, RetailEdge refuses to create another and directs the user to RFQ History.

A different Supplier set is not automatically treated as the same standard sourcing attempt.

Cancelled RFQs do not block a later attempt.

## Stale preview safety

The E1 preview returns the Material Request `modified` timestamp.

Standard submit requires that token and rechecks it after acquiring the Material Request lock.

If the Material Request changed after preview, submission stops and the user must refresh the preview.

## EdgeSuite experience

The RFQ preview now exposes `Create & Submit RFQ` only when the current user has ERPNext RFQ submit permission.

The standard action:

- submits through a POST request;
- stays inside the EdgeSuite modal;
- does not open the native RFQ form;
- reports the submitted ERPNext RFQ number;
- explicitly states that no Supplier email was sent;
- directs normal review to RFQ History.

Users without submit permission may still inspect the preview but are told that submission permission is required.

## Advanced ERPNext fallback

The existing Advanced path remains separate:

`Advanced: Prepare Draft in ERPNext`

It is visible only to users whose shared EdgeSuite access mode permits Native Desk.

The advanced endpoint remains draft-only and branch-safe. It does not submit and does not send Supplier email.

## Safety rules

RIR2F2E3 does **not**:

- send Supplier email;
- create or modify Supplier portal users;
- implement supplier communication templates;
- edit RFQ terms, contacts, addresses or communication settings inside EdgeSuite;
- create Supplier Quotations;
- compare quotations;
- bypass ERPNext Supplier Scorecard / eligibility validation;
- use `ignore_permissions=True`;
- write GL Entry or Stock Ledger Entry;
- modify Purchase Order, Purchase Receipt, Purchase Invoice or payment behavior;
- add schema or migration patches.

ERPNext `Request for Quotation.validate()` and `submit()` remain authoritative.

## Remaining sourcing gaps

After this slice is frozen, audit these as separate bounded slices:

1. Supplier Quotation read/history ownership;
2. standard Supplier Quotation capture where ordinary RetailEdge users require it;
3. quotation-comparison ownership;
4. deliberate supplier email / portal communication workflow, if ProcessEdge chooses to own that experience;
5. RFQ amendment, cancellation and advanced communication/terms workflows.

## Required validation

Freeze only when the same exact SHA passes:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 standalone CI and full RetailEdge test suite;
- governed EdgeSuite UI candidate compatibility.

Manual browser/persona QA remains separate and must not be claimed from automated gates.
