# RIR2F2E4 — Supplier Quotation History Ownership

## Goal

Make routine Supplier Quotation review available inside Professional Purchasing without exposing the native ERPNext Supplier Quotation list as a peer everyday route.

## Frozen parent

RIR2F2E3 standard RFQ submission is frozen at:

`6b01c712b3da7f597abf9029f52343d2feb3bbc7`

## Business contract

A buyer working in RetailEdge should be able to review supplier quotations without leaving EdgeSuite. Native ERPNext remains available only for deliberate advanced document review and the existing Supplier Quotation Comparison report.

## EdgeSuite ownership

The existing `Supplier Quotations` action is capture-intercepted and presented as `Supplier Quote History`.

The EdgeSuite history shows bounded, sortable quotation information including:

- quotation reference;
- transaction date;
- supplier;
- linked RFQ references;
- branch attribution where available;
- quotation total and currency;
- validity date;
- status.

The normal history surface does not persist, submit, amend or cancel Supplier Quotations.

## Scope and permission safety

The backend uses permission-aware `frappe.get_list` for Supplier Quotation and Request for Quotation reads.

Company, Branch and Supplier filters are resolved through the existing Professional Purchasing scope contract.

ERPNext v16 does not guarantee a standard Branch field on Supplier Quotation. Therefore:

1. If a valid Supplier Quotation branch field exists, normal branch-scoped filtering is used.
2. If no Supplier Quotation branch field exists and the user is restricted or explicitly selects a Branch, visibility fails closed to quotations linked through Supplier Quotation Item rows to RFQs inside the permitted Company/Branch scope.
3. Standalone Supplier Quotations without an attributable permitted RFQ are excluded for restricted or branch-filtered users.
4. An unrestricted company-wide user may still see standalone company quotations.
5. RFQ names discovered through child tables are returned only when the current user can also read the RFQ through permission-aware queries.

This avoids treating child-table discovery as permission authority.

## Native Desk rule

For EdgeSuite-only users:

- Supplier Quotation history stays inside EdgeSuite;
- native Supplier Quotation form/list routes remain blocked by the shared operational guard;
- Supplier Quotation Comparison is not exposed.

For Native-Desk-authorized users, explicit secondary actions may appear:

- `Advanced: Open in ERPNext`;
- `Advanced: Supplier Quotations in ERPNext`;
- `Advanced: Compare Quotations in ERPNext`.

These are not routine navigation owners.

## Out of scope

RIR2F2E4 does not implement:

- Supplier Quotation creation or submission;
- supplier portal response entry;
- quotation comparison inside EdgeSuite;
- automatic supplier selection;
- Purchase Order conversion from a Supplier Quotation;
- tax, pricing-rule or currency editing;
- supplier scorecard changes;
- accounting or stock posting;
- reporting development.

## Files

- `retailedge/professional_supplier_quotation.py`
- `retailedge/public/js/professional_purchasing/ProfessionalSupplierQuotationHistoryOverlay.vue`
- `retailedge/public/js/professional_purchasing.bundle.js`
- `retailedge/tests/test_rir2f2e4_supplier_quotation_history_contract.py`
- `docs/rir2f2e4_supplier_quotation_history.md`

## Validation required before freeze

The exact final SHA must pass:

1. RetailEdge Theme Compatibility
2. Linters / pre-commit / Semgrep / dependency audit
3. Clean Frappe v16 CI with the full RetailEdge test suite
4. Governed EdgeSuite UI Candidate Compatibility with the full RetailEdge test suite

Manual browser/persona QA is still required later and is not claimed by automated gates.

## Next boundary

After E4 is green, audit whether Supplier Quotation Comparison should receive an EdgeSuite comparison surface or remain an advanced ERPNext report for MVP. Do not assume promotion until its business value, branch safety and report-data contract are verified.
