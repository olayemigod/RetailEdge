# Pre-reporting Customer Receivables read-scope contract

## Business goal

Customer Receivables context, options, rows, summaries, pagination, exports and intentional read-only consumers may expose submitted Sales Invoice outstanding balances only inside the current reader's authorised Company and operational Branch scope. Client-supplied defaults and filters remain selections, never authority.

## B4B14 scope

This slice replaces Customer Receivables' residual legacy empty-list Branch convention with the B3 operational Branch authority. It covers initial context, Branch options, permission-scoped Sales Invoice headers, the shared page/export dataset, collections enrichment after the permitted population is known, and existing read-only consumers that intentionally reuse this authority. It does not change receivables calculations, collection actions, Payment Request or Dunning behavior, accounting truth, dashboards, navigation, document permissions or reporting capabilities.

## Company and Branch contract

- Company remains mandatory and native Company/Sales Invoice read permission remains required.
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

## Composition and safety boundaries

- Branch options continue through the bounded, permission-aware operational query.
- Page and export reuse one scoped dataset builder.
- Customer 360, Customer Sales Intelligence, Cash Flow Outlook, Liquidity Control, Planning Intelligence, Money Dashboard, Owner Dashboard and Receivables Control continue to reuse the hardened receivables read authority without composition changes.
- Collection enrichment runs only after permission-scoped Sales Invoice rows are known.
- Current-outstanding conversion, ageing buckets, overdue summaries, customer totals, ordering, scan/page/export limits and collection metadata remain unchanged.
- No Sales Invoice, Payment Request, Dunning, Customer, Company, Branch, GL Entry, Payment Entry or other document is mutated.
- No collection action or reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: page, export and dashboard previews contain only that Branch.
2. Restricted reader with multiple Branches: a blank internal read never exceeds the allowed union, while explicit unauthorised selection fails closed.
3. Restricted reader with zero active Branches: no Sales Invoice rows or collection enrichment data are returned.
4. Stale default Branch: context removes it and selects only one unambiguous active assignment.
5. Unrestricted manager with blank Branch: Company-wide current outstanding balances remain available.
6. Missing Sales Invoice Branch attribution: restricted reads fail before a broader query runs.
7. Compare page and export totals for identical Company/Branch/customer/ageing filters; they must reconcile to the same permitted invoice population.
8. Confirm Customer 360, Customer Sales Intelligence, Cash Flow Outlook, Liquidity Control, Planning Intelligence, Money Dashboard, Owner Dashboard and Receivables Control inherit the same scope.
9. Confirm Payment Request/Dunning metadata and ageing/current-outstanding calculations remain equivalent inside the authorised scope.
10. Confirm no collection, accounting or business document is mutated by any read path.
