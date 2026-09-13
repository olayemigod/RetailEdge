# RIR2F2E1 — Sourcing / RFQ EdgeSuite Preview Ownership

## Goal

Close the sourcing dead-end where an EdgeSuite-only buyer could start a Request for Quotation from a Purchase Material Request, persist an ERPNext RFQ draft, and then be routed to a native RFQ form that the shared EdgeSuite-only operational guard correctly blocks.

This slice makes RFQ initiation EdgeSuite-first without claiming full RFQ submission or supplier-communication parity.

## Frozen parent

RIR2F2D3 Purchase Receipt History:

`e09332cdee0efa355a2b1879aa1475ae86b7b751`

## Scope

### Material Request queue ownership

Professional Purchasing already owns a Company/Branch-scoped queue of submitted Purchase Material Requests with remaining procurement quantity.

RIR2F2E1 keeps that queue as the normal operational read surface:

- the Material Request number is a non-routing EdgeSuite reference;
- ordinary `Open` is not exposed to EdgeSuite-only users;
- Native-Desk-authorised users may use an explicit `Advanced: Open in ERPNext` action;
- `Start RFQ` remains the normal sourcing action.

### RFQ preview

`Start RFQ` is capture-intercepted before the legacy Vue handler can create or route a document.

The EdgeSuite RFQ preview:

- selects one or more permitted Suppliers;
- uses ERPNext `make_request_for_quotation()` in memory;
- verifies Purchase Material Request status and remaining quantity;
- verifies mapped RFQ Company and source-item provenance;
- carries Branch attribution when the RFQ DocType supports it;
- fails closed for a restricted user when the named Material Request has no Branch attribution;
- returns mapped items, quantities, UOM, required date and stock location;
- sends no email;
- inserts, saves and submits nothing.

The preview returns:

- `persistence = none`
- `status = Preview only`
- `email_sending = false`

## Advanced ERPNext fallback

Full RFQ review/submission remains Advanced ERPNext work in this slice.

Only a user with Native Desk capability is shown:

`Advanced: Prepare Draft in ERPNext`

The fallback calls a new branch-safe POST-only endpoint in `professional_sourcing.py` instead of the older additive guided endpoint.

The advanced endpoint:

- revalidates Material Request read permission;
- revalidates RFQ create permission;
- validates every selected Supplier;
- fails closed for restricted blank-Branch source documents;
- re-runs ERPNext's RFQ mapper;
- sets `send_email = 0` for every Supplier;
- inserts a draft only;
- never submits or sends Supplier email.

## Safety rules

RIR2F2E1 does **not**:

- submit an RFQ;
- send Supplier email;
- create Supplier Quotations;
- compare quotations inside EdgeSuite;
- change Purchase Order, Purchase Receipt or Purchase Invoice behavior;
- modify accounting or Stock Ledger behavior;
- bypass ERPNext permissions;
- use `ignore_permissions=True`;
- weaken the shared EdgeSuite-only native-route guard.

## Out of scope / next sourcing slices

Still pending after RIR2F2E1:

1. EdgeSuite RFQ history/read ownership.
2. Standard RFQ review/submission if a safe bounded parity contract is approved.
3. Supplier Quotation history/read ownership.
4. Supplier response / quotation entry workflow if required for ordinary users.
5. Quotation comparison ownership.
6. Advanced sourcing communication, terms and exceptional ERPNext workflows.

These should be implemented as separate bounded slices rather than folded into this preview checkpoint.

## Required validation

Freeze only when the same exact SHA passes:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 standalone CI and full RetailEdge test suite;
- governed EdgeSuite UI candidate compatibility.

Manual browser/persona QA remains separate and must not be claimed from automated gates.
