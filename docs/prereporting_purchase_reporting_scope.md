# Pre-reporting Purchase Reporting read-scope contract

## Business goal

Purchase Register and Supplier Payables context, options, rows, summaries, pagination and exports may expose submitted Purchase Invoices only inside the current reader's authorised Company and operational Branch scope. Client-supplied defaults and filters remain selections, never authority.

## B4B12 scope

This slice replaces the purchase reporting engine's residual legacy empty-list Branch convention with the B3 operational Branch authority. It covers the shared Purchase Reporting context, Branch and Warehouse selectors, Purchase Invoice header query, Purchase Register and Supplier Payables page/export paths, plus consumers that intentionally reuse the same permitted Purchase Invoice header helper. It does not change purchase calculations, item aggregation, payables ageing, current-outstanding semantics, payment handoff, purchase-cycle verification, navigation, accounting documents or reporting capabilities.

## Company and Branch contract

- Company remains mandatory for Purchase Register and Supplier Payables reads.
- Native Company and Purchase Invoice read permission remains required before row data is returned.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- A valid authorised default Branch remains selected in the initial context.
- A stale or unauthorised restricted default is removed; exactly one active allowed Branch is selected only when unambiguous.
- An unrestricted reader with a blank Branch retains the Company-wide read.
- A restricted reader with one active Branch and a blank Branch reads only that Branch.
- A restricted reader with multiple active Branches and a blank Branch reads only the allowed union.
- A restricted reader with zero active Branches receives an impossible Purchase Invoice predicate.
- An explicit unauthorised Branch is rejected and an authorised explicit Branch is revalidated against Company→Branch setup.
- Restricted reads fail closed when Purchase Invoice has no usable Branch attribution field.

## Options, composition and safety boundaries

- Branch and Warehouse option searches continue through the bounded, permission-aware operational queries hardened with Stock Movement scope.
- Purchase Register rows, summaries, pagination and exports reuse one dataset builder.
- Supplier Payables page/export variants reuse the same scoped Purchase Invoice header builder and preserve current ERPNext outstanding-balance semantics.
- The existing operating-report wrappers continue to constrain direct whitelisted screen/export filters before dispatch; their reconciled composition is unchanged.
- Purchase Invoice Item reads occur only after permission-scoped parent invoice names are known.
- Invoice/return signs, tax and outstanding conversion, ageing buckets, date filters, item filters, scan limits and page/export limits remain unchanged.
- No Purchase Invoice, Purchase Invoice Item, Supplier, Warehouse, Company, Branch, GL Entry, Payment Entry or other document is mutated.
- No reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: both pages and exports contain only that Branch.
2. Restricted reader with multiple Branches: selected Branch is required by the governed screen/export wrapper; direct shared-engine reads never exceed the allowed union.
3. Restricted reader with zero active Branches: no Purchase Invoice rows are returned and Branch/Warehouse options expose no unauthorised values.
4. Explicit unauthorised Branch: Purchase Register and Supplier Payables page/export requests fail closed.
5. Stale default Branch: context removes it and selects only one unambiguous active assignment.
6. Unrestricted manager with blank Branch: Company-wide results remain available.
7. Missing Purchase Invoice Branch attribution: restricted reads fail before a broader query runs.
8. Warehouse outside Company or selected Branch: server rejects the filter.
9. Compare page and export totals for identical Company/Branch/date filters; they must reconcile to the same permitted invoice population.
10. Confirm payables remain current ERPNext outstanding balances and no purchase/accounting document changes after reads.
