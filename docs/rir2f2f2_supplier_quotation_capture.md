# RIR2F2F2 — Standard RFQ Supplier Quotation Capture

## Status

Implementation checkpoint. Freeze this slice only when Theme Compatibility, Linters, Clean Frappe CI, and governed EdgeSuite UI Candidate Compatibility all pass on one exact commit SHA.

## Business goal

A routine RetailEdge buyer must be able to record a supplier quotation received by email, WhatsApp, phone follow-up, paper, or another off-portal channel without being forced into ERPNext Desk.

The normal path is deliberately bounded to a response against an existing submitted Request for Quotation (RFQ). RetailEdge does not introduce a second generic Supplier Quotation editor.

## Standard EdgeSuite path

1. Open **RFQ History** in Professional Purchasing.
2. Select **Record Supplier Quote** on a submitted RFQ.
3. Choose one Supplier already listed on that RFQ.
4. RetailEdge asks ERPNext to map the RFQ to a native Supplier Quotation draft.
5. Review the mapped RFQ items and enter one quoted rate for every mapped RFQ item.
6. Optionally enter the supplier's quotation/reference number and validity date.
7. Choose **Record & Submit Supplier Quotation**.
8. RetailEdge inserts the mapped native Supplier Quotation and calls its normal ERPNext `submit()` method.

The submitted quotation then appears in the existing Supplier Quotation History, where the frozen Supplier Quotation → Purchase Order draft path remains authoritative.

## ERPNext source of truth

RetailEdge reuses ERPNext v16 `make_supplier_quotation_from_rfq()` so RFQ item lineage remains native:

- `request_for_quotation`
- `request_for_quotation_item`
- Supplier and Company context
- native Supplier Quotation validation and totals

RetailEdge changes only the supplier-provided quoted rate for each mapped RFQ item plus the standard quotation date, optional validity date, and optional supplier reference.

The write path uses normal ERPNext document operations:

- `mapped.insert()`
- `mapped.submit()`

Supplier Quotation submission remains ERPNext-authoritative. ERPNext updates the quotation status and RFQ supplier response status through its standard `on_submit()` logic.

## Safety rules

The standard RetailEdge path fails closed when any of the following applies:

- the RFQ is not submitted;
- the user cannot read the RFQ or Company;
- the chosen Supplier is not a Supplier on the RFQ;
- the user lacks Supplier Quotation create or submit permission;
- an active ERPNext Supplier Quotation approval Workflow exists;
- a non-cancelled Supplier Quotation already exists for the same Supplier and RFQ;
- the mapped Supplier Quotation is subcontracted;
- a restricted user receives an RFQ with no usable Branch attribution;
- the RFQ changed after the user's review;
- the submitted rate payload does not exactly match the mapped RFQ item set;
- a quoted rate is negative;
- Valid Till is earlier than the quotation date.

Duplicate detection may discover an existing quotation through child-row lineage, but the existing quotation name is only disclosed when the user can read it.

## Branch and scope contract

The RFQ remains the operational source of Branch scope for this path.

- When the RFQ has a Branch, RetailEdge revalidates the user's access server-side.
- Restricted users fail closed when the RFQ has no Branch attribution.
- If Supplier Quotation has a compatible Branch field, the mapped quotation inherits the RFQ Branch.
- If Supplier Quotation has no Branch field, RFQ item lineage remains the authoritative scope relationship, consistent with the existing Supplier Quotation History contract.

Frontend visibility is not treated as security.

## Deliberately Advanced / out of scope

The following remain deliberate ERPNext Advanced workflows:

- ad-hoc Supplier Quotations not originating from an RFQ;
- Supplier Quotation approval Workflows;
- subcontracting quotations;
- adding/removing items outside the RFQ;
- special tax, charge, discount, currency, exchange-rate, pricing-rule, address, contact, terms, or accounting-dimension changes;
- amendment/cancellation of submitted Supplier Quotations;
- supplier portal communication mechanics.

These cases must not be simplified by bypassing ERPNext validation or governance.

## Accounting and stock safety

This slice does not:

- create or mutate Purchase Orders, Purchase Receipts, or Purchase Invoices;
- create Payment Entries;
- post General Ledger Entries;
- post Stock Ledger Entries;
- mutate submitted accounting documents;
- reproduce ERPNext Supplier Quotation submit side effects manually.

Supplier Quotation is a sourcing document. Any later PO, receipt, invoice, payment, GL, or stock effect remains in the existing authoritative ERPNext workflow.

## Backward compatibility

Preserved unchanged:

- RFQ creation and RFQ History;
- native Advanced RFQ access for authorized users;
- Supplier Quotation History;
- Supplier Quotation → Purchase Order draft conversion;
- Purchase Order guided create and standard submit;
- Purchase Receipt handling;
- supplier invoice document review;
- returns, landed cost, incoming quality, supplier scorecards, and other advanced purchasing capabilities.

No DocType schema, patch, migration, role definition, accounting configuration, or branch-core contract changes are introduced.

## Tests required

### Focused/unit contract

- preview is read-only and uses ERPNext RFQ → Supplier Quotation mapping;
- supplier must belong to the RFQ;
- exact mapped RFQ item/rate contract is enforced;
- active Workflow and permission blockers are enforced;
- duplicate supplier+RFQ quotation is blocked;
- restricted blank-Branch RFQ fails closed;
- POST write locks/revalidates the RFQ and rejects stale review tokens;
- write path calls native insert + submit and contains no manual GL/SLE logic;
- EdgeSuite capture never routes to native Desk during the standard operation.

### Integration/regression

- full RetailEdge suite;
- clean Frappe v16 install/migrate/build;
- governed EdgeSuite UI candidate suite;
- Theme Compatibility;
- Linters/pre-commit/Semgrep/dependency audit.

### Migration

No migration is required. Clean install and `bench migrate` must remain green.

### Manual QA still required before final persona sign-off

For a permitted Purchase User/Manager persona:

- open RFQ History;
- record a response for a submitted RFQ with one Supplier;
- record a response for an RFQ with multiple Suppliers and verify supplier selection is constrained to that RFQ;
- verify every mapped item requires a rate and no extra item can be introduced;
- confirm successful creation produces a submitted Supplier Quotation in history;
- confirm the RFQ supplier response status updates through ERPNext;
- confirm the submitted quotation can proceed through the existing Prepare PO path;
- confirm duplicate, stale, restricted blank-Branch, missing-permission, and active-Workflow cases fail closed;
- confirm EdgeSuite-only users are not routed to native Desk during the standard flow.

## RIR2F2 purchasing closure rule

Once this slice is frozen green, routine Purchasing is considered closed for pre-reporting composition. Advanced ERPNext purchasing capabilities remain intentionally Advanced unless a separate routine-user dead-end is proven.

The next planned phase is **RIR2F3 Payments hardening/audit**, not reporting development.
