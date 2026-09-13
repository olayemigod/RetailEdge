# RIR2F2E5 — Supplier Quotation to Purchase Order Draft

## Goal

Close the normal sourcing handoff from an accepted submitted Supplier Quotation into a Purchase Order without forcing EdgeSuite-only buyers into ERPNext Desk and without reimplementing ERPNext quotation pricing, taxes, item references or Purchase Order validation.

## Ownership contract

For the standard path:

1. Supplier Quotation History remains the EdgeSuite read/review owner.
2. An eligible submitted Supplier Quotation exposes **Prepare PO**.
3. RetailEdge previews ERPNext's native `Supplier Quotation -> Purchase Order` mapping without saving anything.
4. The user may create exactly one draft Purchase Order from that fresh preview.
5. The resulting Purchase Order remains a draft. Submission is not part of RIR2F2E5.

Native Supplier Quotation forms and the Supplier Quotation Comparison report remain explicit Advanced ERPNext surfaces where previously authorized.

## ERPNext source of truth

RIR2F2E5 calls:

`erpnext.buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order`

RetailEdge does not copy or recalculate the Supplier Quotation's agreed rates or tax rows. ERPNext's mapper remains authoritative for:

- Supplier and Company;
- quotation item references;
- quantities and UOMs;
- agreed rates and amounts;
- taxes and charges;
- schedule-date defaults;
- Purchase Order validation during insert.

## Server-side safety

The conversion backend requires:

- read permission on the named Supplier Quotation;
- submitted Supplier Quotation (`docstatus = 1`);
- quotation status not Cancelled, Stopped or Expired;
- create permission on Purchase Order;
- fresh source `modified` token at draft creation time;
- a row lock on the Supplier Quotation during creation;
- no existing active Purchase Order referencing the same Supplier Quotation;
- Company and Supplier equality between source and mapped Purchase Order;
- every mapped PO item to reference the selected Supplier Quotation;
- a single safe Branch attribution for restricted operation.

The action uses normal `purchase_order.insert()` as the current user. It does not use `ignore_permissions=True`, `frappe.db.commit`, direct Stock Ledger Entry writes, or direct GL Entry writes.

## Branch contract

Supplier Quotation has no guaranteed standard Branch field in ERPNext v16.

RetailEdge therefore resolves Branch as follows:

1. If Supplier Quotation has an applicable Branch field, use and validate it.
2. Otherwise derive Branch from linked Requests for Quotation.
3. Every linked RFQ must be readable by the current user and belong to the same Company.
4. Restricted users fail closed if the sourcing chain has no attributable Branch.
5. Quotations spanning more than one Branch are rejected from this standard path and require Advanced ERPNext review.
6. A direct Supplier Quotation Branch and linked RFQ Branch must agree when both exist.
7. Unrestricted users may create a company-wide draft only when no Branch can be derived.

If a Branch is resolved, it is copied onto the mapped Purchase Order using the established RetailEdge Purchase Order branch field contract.

## Duplicate safety

The draft endpoint locks the Supplier Quotation row before duplicate detection and mapping. If an active Purchase Order already references the quotation, creation is blocked.

The preview returns only a boolean duplicate indicator. It does not expose an existing Purchase Order identifier discovered through child-table lookup.

## EdgeSuite behavior

Supplier Quotation History now provides **Prepare PO** only for submitted quotations whose status is not Cancelled, Stopped or Expired.

The conversion overlay shows:

- source Supplier Quotation;
- Supplier;
- Company;
- resolved Branch;
- mapped total;
- mapped item count;
- item quantities, UOMs, rates, amounts, dates and warehouses;
- mapped tax-row count.

The normal action is **Create Draft Purchase Order**.

Successful creation stays inside EdgeSuite, refreshes Professional Purchasing and refreshes Supplier Quotation History. It does not automatically route to an ERPNext Purchase Order form.

## Out of scope

RIR2F2E5 does not:

- submit the Purchase Order;
- receive stock;
- create a Purchase Invoice;
- mutate a submitted Supplier Quotation;
- perform quotation comparison;
- choose a winning quotation automatically;
- merge multiple Supplier Quotations into one Purchase Order;
- handle a quotation spanning multiple Branches;
- replace advanced ERPNext Purchase Order review.

## Tests required

Contract tests freeze:

- ERPNext `make_purchase_order` mapper ownership;
- preview non-persistence;
- submitted/status gating;
- Branch fail-closed behavior;
- POST-only row-locked draft creation;
- stale-source rejection;
- duplicate protection;
- draft-only insert with no submit;
- no direct ledger writes or permission bypass;
- EdgeSuite `Prepare PO` eligibility;
- no normal native redirect after creation;
- mounting/cleanup of the conversion overlay.

Exact-head validation requires Theme Compatibility, Linters, clean Frappe v16 CI, and governed EdgeSuite UI Candidate Compatibility.

## Manual QA still required

Automated gates do not replace browser/persona QA. Before final pre-reporting freeze, verify at least:

- EdgeSuite-only Purchase User/Manager;
- Native-Desk-authorized advanced buyer;
- restricted one-Branch user;
- unrestricted/company-wide user;
- submitted valid quotation;
- draft/expired quotation unavailable for Prepare PO;
- duplicate quotation-to-PO attempt blocked;
- quotation rates/taxes retained in the created draft;
- no automatic native navigation;
- clean console/network behavior in representative light/dark themes.

Reporting remains blocked until the wider pre-reporting hardening and persona QA sequence is complete.
