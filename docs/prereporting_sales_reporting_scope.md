# Pre-reporting Sales Reporting read-scope contract

## Business goal

Sales by Item and Sales Invoice Register context, options, rows, summaries, pagination and exports may expose submitted Sales Invoices only inside the current reader's authorised Company and operational Branch scope. Client-supplied defaults and filters remain selections, never authority.

## B4B13 scope

This slice replaces the sales reporting engine's residual legacy empty-list Branch convention with the B3 operational Branch authority. It covers shared Sales Reporting context, Branch and Warehouse selectors, the Sales Invoice header query, Sales by Item and Sales Invoice Register page/export paths, plus existing consumers that intentionally reuse the permitted Sales Invoice header helper. It does not change sales calculations, return handling, item aggregation, Sales Team allocation, customer intelligence, profitability logic, navigation, accounting documents or reporting capabilities.

## Company and Branch contract

- Company remains mandatory for Sales by Item and Sales Invoice Register reads.
- Native Company and Sales Invoice read permission remains required before row data is returned.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- A valid authorised default Branch remains selected in the initial context.
- A stale or unauthorised restricted default is removed; exactly one active allowed Branch is selected only when unambiguous.
- An unrestricted reader with a blank Branch retains the Company-wide read.
- A restricted reader with one active Branch and a blank Branch reads only that Branch.
- A restricted reader with multiple active Branches and a blank Branch reads only the allowed union.
- A restricted reader with zero active Branches receives an impossible Sales Invoice predicate.
- An explicit unauthorised Branch is rejected and an authorised explicit Branch is revalidated against Company→Branch setup.
- Restricted reads fail closed when Sales Invoice has no usable Branch attribution field.

## Options, composition and safety boundaries

- Branch and Warehouse option searches continue through the bounded, permission-aware operational queries hardened with Stock Movement scope.
- Sales by Item and Sales Invoice Register page/export pairs each reuse one scoped dataset builder.
- The existing operating-report wrappers continue to constrain direct whitelisted screen/export filters before dispatch; their reconciled composition is unchanged.
- Sales Invoice Item and Sales Team reads occur only after permission-scoped parent invoice names are known.
- Existing customer intelligence, profitability, forecasting and dashboard consumers inherit the same permitted Sales Invoice population without composition changes.
- Invoice/return signs, tax and outstanding conversion, quantities, average selling price, Sales Team allocation, date/item/customer/status filters and scan/page/export limits remain unchanged.
- No Sales Invoice, Sales Invoice Item, Sales Team, Customer, Warehouse, Company, Branch, GL Entry, Payment Entry or other document is mutated.
- No reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: both pages and exports contain only that Branch.
2. Restricted reader with multiple Branches: governed screen/export wrappers require an authorised selection; shared internal reads never exceed the allowed union.
3. Restricted reader with zero active Branches: no Sales Invoice rows are returned and Branch/Warehouse options expose no unauthorised values.
4. Explicit unauthorised Branch: Sales by Item and Sales Invoice Register page/export requests fail closed.
5. Stale default Branch: context removes it and selects only one unambiguous active assignment.
6. Unrestricted manager with blank Branch: Company-wide results remain available.
7. Missing Sales Invoice Branch attribution: restricted reads fail before a broader query runs.
8. Warehouse outside Company or selected Branch: server rejects the filter.
9. Compare page and export totals for identical Company/Branch/date filters; they must reconcile to the same permitted invoice population.
10. Confirm returns, salesperson allocations and customer intelligence outputs remain calculation-equivalent inside the authorised scope, with no document mutation.
