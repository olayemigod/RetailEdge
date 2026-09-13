# RIR2G1D — Standard Sales Invoice Completion

## Goal

Remove the ordinary EdgeSuite dead end after a standard Sales Invoice draft is created, while preserving ERPNext as the sole authority for receivable, tax, General Ledger, outstanding amount, status and any stock-posting consequences.

RIR2G1D applies to both standard RetailEdge entry surfaces:

- Professional Selling Sales Invoice creation/conversion;
- Business Hub Simple Sales Invoice.

It does not replace ERPNext accounting logic.

## Standard Business Boundary

Supported draft sources include:

- new standard Sales Invoice;
- direct accepted Customer Quotation → Sales Invoice draft;
- submitted Sales Order → Sales Invoice draft;
- submitted Delivery Note → Sales Invoice draft;
- Simple Sales Invoice draft.

Return / Credit Note completion remains Advanced ERPNext for this checkpoint.

## Standard Eligibility

A Sales Invoice may use RIR2G1D only when:

- it is a draft Sales Invoice;
- it is not a return / Credit Note;
- it is not amended;
- it is not POS/consolidated;
- it is not internal/inter-company;
- it has a Customer and at least one item;
- no automatic/manual write-off amount is configured;
- no advance-allocation rows are already attached;
- any linked Sales Order / Delivery Note source is readable, submitted and matches Company, Customer and operational Branch;
- it satisfies the accounting-only or stock-updating contract below.

Shipping Rule, ERPNext taxes/payment terms and RetailEdge-supported loyalty redemption remain valid standard draft content. ERPNext revalidates all of them on submit.

## Accounting-only Invoice

When `update_stock = 0`:

- Warehouse is not required merely for completion;
- no RetailEdge Stock Ledger validation or posting engine is introduced;
- ERPNext native submit remains authoritative for receivable, tax, GL and outstanding amount;
- linked source documents, when present, are revalidated and never mutated directly.

## Stock-updating Invoice

When `update_stock = 1`:

- every invoice item must have a Warehouse;
- every Warehouse must be readable, same-Company and resolve to one permitted operational Branch;
- resolved Warehouse Branch must match the invoice/source operational Branch;
- a Sales Invoice linked to a submitted Delivery Note must not also update stock;
- Serial No, Batch No or Serial-and-Batch-Bundle state is Advanced ERPNext;
- Product Bundle / packed-item stock posting is Advanced ERPNext in this checkpoint;
- ERPNext native submit is the only Stock Ledger/valuation authority.

## Source Documents

If a standard draft contains source references:

- Delivery Note references take precedence as the fulfilment source;
- otherwise Sales Order references may be validated;
- source documents must be submitted, readable, same Company and Customer;
- attributed Branches must pass current operational Branch authority and match the invoice Branch when both are present;
- source documents remain submitted and unchanged.

Standalone invoices and direct Quotation invoices may have no Sales Order/Delivery Note link and remain valid when otherwise standard.

## Preview

Completion review is persistence-free and exposes:

- Sales Invoice identity and immutable `modified` snapshot;
- Company, Branch and Customer;
- `update_stock` mode;
- source summary when linked;
- item/total summary;
- standard-shape/accounting/stock blockers;
- Frappe Workflow readiness;
- whether native direct submit is currently available.

Preview must not save, insert, submit or mutate anything.

## No Active Workflow

Direct submit is permitted only after:

1. row lock of the exact Sales Invoice;
2. immutable snapshot stale check;
3. Company/Branch/source/stock context revalidation;
4. standard-shape blockers are empty;
5. submit permission check;
6. confirmation that no active Frappe Workflow owns the document.

RetailEdge then calls only `doc.submit()`.

ERPNext owns all accounting, receivable, tax, GL, outstanding and stock effects.

## Active Frappe Workflow

When active Frappe Workflow exists:

- direct submit fails closed;
- only Frappe-returned `available_actions` are shown;
- workflow progression delegates through the shared F3F27 bridge;
- immutable `modified` and expected workflow state are supplied;
- EdgeSuite never assigns `workflow_state` or `docstatus`.

## UI Ownership

Professional Selling:

- saved standard Sales Invoice opens completion review;
- recent permitted draft Sales Invoice exposes Review Completion;
- Return / Credit Note drafts do not receive standard completion controls from this checkpoint.

Business Hub:

- Simple Sales Invoice save opens the same standard completion review;
- EdgeSuite-only users do not require Native Desk for standard completion;
- Advanced ERPNext is shown only when Native Desk capability exists.

## Scope

Runtime:

- `retailedge/standard_sales_invoice_completion.py`
- `retailedge/public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue`
- `retailedge/public/js/professional_selling/ProfessionalSelling.vue`
- `retailedge/public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue`

Reused authorities:

- `retailedge/professional_sales_invoice.py`
- `retailedge/guided_sales_invoice.py`
- `retailedge/professional_selling.py`
- `retailedge/workflow_readiness.py`
- `retailedge/workflow_actions.py`

## Out of Scope

- Sales Return / Credit Note completion;
- POS Invoice lifecycle;
- consolidated invoices;
- amendments/cancellation;
- automatic/manual write-off;
- pre-attached advance allocation;
- Serial/Batch/Serial-and-Batch-Bundle stock posting;
- Product Bundle / packed-item stock posting;
- inter-company/internal-customer invoices;
- Payment Entry creation/collection;
- Payment Reconciliation;
- direct GL or Stock Ledger logic;
- schema/migration work;
- manual browser/persona acceptance.

## Tests Required

Backend:

1. completion service is Sales Invoice-only;
2. preview is persistence-free;
3. draft non-return standard shape accepted;
4. return/amended/POS/consolidated/internal/inter-company fails closed;
5. write-off/advance allocation fails closed;
6. Customer and Company required;
7. operational Branch is revalidated;
8. source Sales Order/Delivery Note is submitted/readable/same Company/Customer/Branch;
9. accounting-only invoice does not require Warehouse;
10. update-stock invoice requires every Warehouse and one operational Branch;
11. update-stock + Delivery Note source fails closed;
12. Serial/Batch/bundle state fails closed for stock-updating standard completion;
13. packed-item stock update fails closed;
14. active Workflow blocks direct submit;
15. direct submit row-locks, stale-checks, revalidates and delegates only to native `doc.submit()`;
16. workflow action row-locks/stale-checks/revalidates and delegates through F3F27;
17. no direct GL/SLE, write-off posting, outstanding mutation, `ignore_permissions`, manual commit or workflow/docstatus assignment.

UI:

18. Professional Selling saved standard invoice opens completion review;
19. recent draft invoice exposes completion review;
20. Return / Credit Note creation does not auto-open standard completion;
21. Business Hub Simple Sales Invoice opens the same completion review;
22. active Workflow hides direct submit and shows only server actions;
23. successful completion refreshes the owning surface;
24. Advanced ERPNext remains capability-gated.

Regression:

25. existing invoice draft creation/conversion stays draft-only;
26. RIR2G1B/G1C tests remain green;
27. Branch-cascade and payment ownership tests remain green.

## Safety Rules

- no direct General Ledger Entry creation;
- no direct Stock Ledger Entry creation;
- no manual receivable/outstanding mutation;
- no submitted source mutation;
- no `ignore_permissions`;
- no manual DB commit;
- no direct `docstatus` or workflow-state assignment;
- no schema migration.

## Freeze Rule

RIR2G1D may freeze only when all four governed exact-head gates pass on one SHA:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. EdgeSuite UI Candidate Compatibility.

After RIR2G1D freeze, RIR2G1 continues through the remaining customer payment/receivables and sales-to-cash journey boundaries before Phase 2 may be considered code-complete.
