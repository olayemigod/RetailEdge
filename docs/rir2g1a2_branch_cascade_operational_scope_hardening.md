# RIR2G1A2 — End-to-End Branch Cascade and Operational Scope Hardening

## Goal

Make Branch cascade behavior consistent across the RetailEdge MVP's standard EdgeSuite journeys so changing or omitting Branch cannot leave stale dependent values on the frontend or bypass operational Branch scope on the backend.

This is a safety hardening checkpoint inside RIR2G1. It does not change ERPNext accounting, stock, document lifecycle, approval, or posting semantics.

## Parent / Dependent Contract

Branch is an operational parent context.

When Branch changes, only values whose business validity depends on Branch must be cleared, re-resolved, or revalidated.

### Branch-dependent values

Examples include:

- Warehouse / Stock Location;
- branch-attributed Sales/Purchase Invoice references used for Payment Entry;
- mapped source documents and mapped warehouses where Branch attribution is relevant;
- Branch-derived price-list/pricing results;
- Branch-derived Cost Center or other defaults when a workflow explicitly uses those defaults.

### Company-wide values

A Branch change must not automatically clear values merely because they are displayed on the same form when their validity is only Company-scoped, for example:

- a Company-valid Supplier or Customer unless a separate branch-assignment rule exists;
- a Company-valid Bank/Cash Account unless a specific Branch-account restriction is configured;
- a Company-valid Project unless a separate Branch relationship exists.

RetailEdge Branch Profile fields such as default Bank/Cash Account and default Cost Center are defaults. They are not treated as exclusive allowed-value lists by this checkpoint.

## Frontend Audit Result

### Already compliant

The following guided forms already invalidate/re-resolve Branch-dependent state:

- Stock Adjustment: Branch clears/re-resolves Warehouse.
- Stock Transfer: source/target Branch cascades to the corresponding Warehouses.
- Simple Purchase Invoice: Branch clears Warehouse, re-resolves receiving Warehouse, clears stale pricing cache, and reprices items.
- Simple Sales Invoice: Branch clears Warehouse, re-resolves sales Warehouse, and reprices.
- Professional Quotation / Sales Order / Sales Invoice: Branch clears Warehouse, re-resolves Branch/Warehouse and refreshes Branch-dependent pricing.
- Professional Purchase Order: Branch clears receiving Warehouse and refreshes pricing.
- Simple Payment: Branch change clears invoice allocations and customer/supplier submit-review state.
- Business Expense: Company change clears Branch and Company-dependent values; Branch change clears Expense Category / Cost Center defaults that may be Branch-derived.

### Deliberate non-clears

- Simple Cash/Bank Transfer retains From/To Account when Branch changes because the current standard transfer contract validates these as Company Bank/Cash posting accounts, not Branch-exclusive accounts.
- Simple Payment retains Mode of Payment when Branch changes because the current resolver is Company-scoped. Invoice references are cleared because they are Branch-sensitive.

## Confirmed Backend Gaps

### Guided Payment

The current implementation still uses the legacy empty-list Branch convention in Branch search, reference search, reference validation and draft creation.

Consequences under Branch Assignment history:

- restricted-zero can receive a broad Branch filter;
- blank Branch can reach reference search or draft creation;
- an explicitly attributed reference can be validated by the legacy helper that treats an empty legacy branch list as unrestricted.

### Guided Cash / Bank Transfer

Draft creation validates Branch only when a Branch is supplied. A restricted user can POST a blank Branch and create a Company-wide Payment Entry draft.

### Cash Deposit / Cashier Expense custody context

Cash Deposit and Cashier Expense derive Branch from an existing cashier/POS-shift context rather than from a free user selector. That is the correct frontend model, but the derived/stored Branch is still validated through the older generic Branch helper.

Because the source is an existing operational context, this checkpoint must not silently invent a Branch for a shift that has no attribution. For restricted users:

- a populated shift/document Branch must pass current operational Branch authority;
- a missing shift/document Branch must fail closed;
- unrestricted legacy sites may preserve blank-Branch compatibility.

### Standard Customer / Supplier Payment completion

Payment Entry and invoice Branch revalidation still use the legacy branch helper. A stored explicit Branch outside active Branch Assignment scope can therefore be incorrectly accepted when the legacy allowed-Branch list is empty.

### Professional Selling

The shared Professional Selling search/write service has already been partly migrated on the authoritative branch:

- restricted-zero Warehouse search fails closed;
- restricted multi-Branch Warehouse search waits for explicit Branch;
- restricted single Branch may auto-resolve;
- Warehouse-derived Branch is server-revalidated;
- recent-document read scope no longer becomes Company-wide for restricted-zero.

Mapped Quotation → Sales Order, Sales Order → Delivery and source → Sales Invoice helpers still contain legacy explicit-Branch validation calls and must be aligned with the same operational resolver.

## Backend Contract

Use the authoritative operational Branch contract:

- `get_operational_branch_scope(company, user)`
- `resolve_operational_branch(company, branch, user)`

Rules:

1. unrestricted user + blank Branch preserves approved Company-wide behavior;
2. restricted single-Branch + blank Branch may resolve the one active permitted Branch;
3. restricted multi-Branch + blank Branch must require explicit Branch before a Branch-sensitive write or reference selection;
4. restricted-zero must fail closed;
5. explicit Branch is always revalidated against current operational scope;
6. a Branch-attributed Warehouse or source/reference document must be revalidated server-side even if frontend state was previously valid;
7. backend endpoints must not trust frontend clearing/cascade;
8. existing documents with missing Branch attribution cannot be silently rewritten during submit/review; restricted users must fail closed where Branch attribution is required.

## Scope

Runtime:

- `retailedge/guided_payment.py`
- `retailedge/guided_cash_transfer.py`
- `retailedge/cash_custody.py`
- `retailedge/retailedge/doctype/retailedge_cashier_expense/retailedge_cashier_expense.py`
- `retailedge/standard_customer_payment_submit.py`
- `retailedge/standard_supplier_payment_submit.py`
- `retailedge/professional_selling.py` only for existing in-flight cascade hardening
- `retailedge/professional_sales_order.py`
- `retailedge/professional_delivery.py`
- `retailedge/professional_sales_invoice.py`
- `retailedge/guided_entry_context.py` only if a focused resolver correction is required

Frontend:

- contract tests for the existing cascade behavior;
- runtime UI edits only where a stale dependent value is actually demonstrated.

## Out of Scope

- changing Branch Assignment architecture;
- making Branch Profile defaults exclusive permissions;
- filtering Customer/Supplier/Project by Branch without an existing business relation;
- changing Bank/Cash account ownership semantics;
- Delivery Note submit ownership;
- Sales Invoice submit ownership;
- Quotation/Sales Order lifecycle completion beyond preserving the already-started RIR2G1B contract;
- accounting/GL or stock valuation semantics;
- schema migration;
- reporting expansion;
- manual browser/persona QA.

## Tests Required

Frontend contracts:

1. selling/purchasing Branch change clears Warehouse before re-resolution;
2. Branch-driven pricing is invalidated/reloaded;
3. Simple Payment Branch change clears invoice references and payment review state;
4. Stock Adjustment/Transfer keep their existing Branch→Warehouse cascade;
5. Business Expense Branch change clears Branch-derived category/cost-center state;
6. no test requires Company-wide Bank/Cash account values to be cleared solely on Branch change.

Backend contracts:

7. Guided Payment Branch search restricted-zero returns no permitted Branch;
8. Guided Payment reference search restricted-zero does not expose Company-wide invoices;
9. Guided Payment restricted-zero/multi blank-Branch write fails closed;
10. Guided Payment restricted-single blank Branch safely resolves the one active Branch;
11. direct reference-detail lookup revalidates Branch scope;
12. Guided Cash Transfer restricted-zero/multi blank-Branch write fails closed;
13. Guided Cash Transfer restricted-single blank Branch safely resolves;
14. unrestricted Cash Transfer blank Branch preserves Company-wide compatibility;
15. Cash Deposit revalidates the active shift Branch and fails closed for restricted missing attribution;
16. Cashier Expense revalidates its stored/derived Branch and fails closed for restricted missing attribution;
17. standard Customer/Supplier Payment explicit stored Branch is validated with operational Branch authority;
18. restricted Payment Entry with missing Branch attribution fails closed;
19. mapped Selling source Branch and Warehouse-derived Branch use operational Branch authority;
20. restricted-zero recent Selling read does not become Company-wide;
21. no endpoint uses frontend filtering as its only protection.

Safety:

22. no `ignore_permissions`;
23. no manual database commit;
24. no direct GL/SLE write;
25. no submitted accounting/stock document mutation;
26. no schema migration.

## Freeze Rule

RIR2G1A2 may freeze only when all four governed exact-head gates pass:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. clean Frappe v16 CI;
4. governed EdgeSuite UI Candidate Compatibility.

After freeze, resume RIR2G1B Standard Quotation + Sales Order Completion from its already-frozen contract without changing that contract.
