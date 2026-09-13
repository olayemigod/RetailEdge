# RIR2G2B — Guided Purchase Invoice Completion Continuity

## Goal

Close the ordinary Business Hub **Record Purchase** dead end without changing the existing Guided Purchase Invoice creator or overlapping source-driven Professional Purchasing / Supplier Document Purchase Invoice ownership.

`retailedge.guided_purchase_invoice.create_simple_purchase_invoice_draft` remains draft-only.

RIR2G2B adds a separate EdgeSuite completion owner for safe, source-less standard Purchase Invoice drafts and a resumable review surface in Professional Purchasing.

## Ownership Boundary

Supported generic standard Purchase Invoice:

- draft Purchase Invoice;
- direct/source-less purchase;
- created/readable under the current user's ERPNext permissions;
- same Company/operational Branch context;
- Supplier and at least one item;
- accounting-only or ordinary `update_stock` shape defined below.

Explicitly not owned by this generic path:

- Supplier Document → Purchase Invoice immutable handoff;
- Purchase Order-linked Purchase Invoice;
- Purchase Receipt-linked Purchase Invoice;
- return / Supplier Debit Note;
- amended/cancelled invoices;
- inter-company/internal supplier;
- paid-at-source / immediate-payment Purchase Invoice;
- advance allocation;
- opening entries;
- subcontracting;
- Serial/Batch/Serial-and-Batch-Bundle complexity;
- other exceptional accounting/stock cases.

Those remain with their existing governed owner or Advanced ERPNext.

## Accounting-only Purchase Invoice

When `update_stock = 0`:

- Warehouse is not required for completion merely because an invoice is payable;
- ERPNext native submit remains sole authority for payable, tax, GL, Payment Ledger and outstanding amount;
- source-document fields must remain empty for this generic path.

## Stock-updating Purchase Invoice

When `update_stock = 1`:

- every item must have a Warehouse;
- each Warehouse must be readable, same-Company and resolve to permitted operational Branch context;
- all resolved Warehouse Branches must collapse to one Branch and match invoice Branch when attributed;
- Serial No, Batch No, Serial-and-Batch-Bundle and subcontracting/supplied-item complexity fail closed;
- ERPNext native submit remains sole Stock Ledger and valuation authority.

## Preview

The review must be persistence-free and expose:

- Purchase Invoice identity and immutable `modified`;
- Supplier, Company, Branch;
- total/currency;
- accounting-only vs update-stock mode;
- item summary;
- blockers;
- Frappe Workflow readiness;
- direct-submit eligibility.

Preview must not save, insert, submit or mutate anything.

## No Active Workflow

Direct completion must:

1. row-lock the exact Purchase Invoice;
2. stale-check the reviewed `modified`;
3. revalidate Company/Branch/Supplier;
4. revalidate generic source-less shape;
5. revalidate stock context when `update_stock = 1`;
6. verify submit permission;
7. confirm no active Frappe Workflow owns the document;
8. call only ERPNext native `doc.submit()`.

ERPNext remains authoritative for accounting, payable, tax, outstanding, Payment Ledger, Stock Ledger and valuation consequences.

## Active Frappe Workflow

- direct submit fails closed;
- only server-returned `available_actions` are displayed;
- workflow action uses the shared F3F27 bridge;
- immutable `modified` and expected workflow state are supplied;
- EdgeSuite never assigns workflow state or docstatus.

## Resumability

Business Hub:

- after **Record Purchase** saves a draft, open the standard completion review immediately.

Professional Purchasing:

- expose a small permission-aware **Draft Purchase Invoices Awaiting Completion** section;
- list only current-scope draft Purchase Invoices eligible for generic review;
- review uses the same completion dialog/service;
- refresh the list after completion;
- no native-form dependency for EdgeSuite-only users.

This is operational continuity, not Business Hub Phase-4 redesign.

## Scope

- `retailedge/standard_purchase_invoice_completion.py`
- `retailedge/public/js/professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue`
- `retailedge/public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue`
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- focused contract/regression tests

## Out of Scope

- changing Guided Purchase Invoice creation semantics;
- changing Supplier Document Purchase Invoice completion;
- source-driven PO/Receipt Purchase Invoice completion;
- Purchase Return / Debit Note;
- Payment Entry creation;
- Payment Reconciliation;
- complex stock/subcontracting;
- generic Purchase Invoice editing;
- schema/migration work;
- reporting expansion;
- browser/persona QA.

## Tests Required

Backend:

1. service is Purchase Invoice-only;
2. preview is persistence-free;
3. only draft non-return/non-amended direct Purchase Invoice is supported;
4. source Purchase Order/Receipt references fail closed;
5. Supplier Document handoff-linked invoice fails closed;
6. internal/inter-company, opening, immediate-paid and advance-allocation shapes fail closed;
7. Company/operational Branch authority is revalidated;
8. accounting-only invoice does not require Warehouse;
9. update-stock invoice requires Warehouse per item;
10. Warehouses are readable, same Company and one permitted Branch;
11. Serial/Batch/bundle/subcontracting complexity fails closed;
12. active Workflow blocks direct submit;
13. direct submit row-locks, stale-checks, revalidates, checks permission and calls only `doc.submit()`;
14. workflow action revalidates and delegates through F3F27;
15. no direct GL/SLE/Payment Ledger/outstanding mutation, `ignore_permissions` or manual commit;
16. list endpoint is permission-aware, bounded and operational-scope-safe.

UI:

17. Business Hub Record Purchase opens completion after save;
18. Professional Purchasing lists eligible standard draft Purchase Invoices;
19. Professional Purchasing can open the same completion dialog;
20. completion refreshes the resumable draft list;
21. Advanced ERPNext is shown only with Native Desk capability;
22. Supplier Document and Professional Purchasing source-driven flows remain unchanged.

Regression:

23. `guided_purchase_invoice.py` still contains `doc.insert()` and no `doc.submit()`;
24. F3F20/F3F38 Supplier Document completion remains intact;
25. G2A native-navigation containment remains intact.

## Freeze Rule

Freeze only when Theme, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on the same exact runtime SHA.
