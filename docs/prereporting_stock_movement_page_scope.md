# Pre-reporting Stock Movement History page-context scope contract

## Business goal

Stock Movement History must initialise Company, Branch and Warehouse defaults from the same current-reader operational authority already used by its report resolver and option queries. A stale client/default selection must never broaden the subsequent Stock Ledger read.

## B4B16 scope

This slice replaces the EdgeSuite page context's residual legacy empty-list Branch convention with the B3 operational Branch authority. It aligns initial Branch selection and default Warehouse resolution with the already-hardened Stock Movement History report/page/export and shared Branch/Warehouse searches. It does not change Stock Ledger retrieval, opening balances, reconciliation treatment, running balances, movement classification, UOM conversion, display filters, guided Stock Transfer, stock posting, navigation or reporting capability.

## Context contract

- Company remains the readable user default; an unreadable or absent Company yields no Branch or Warehouse default.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback through the operational scope helper.
- A valid authorised default Branch remains selected.
- A stale or unauthorised restricted default is removed; exactly one active allowed Branch is selected only when unambiguous.
- Restricted multi-Branch or zero-active-Branch context remains blank and cannot trigger Warehouse autofill.
- An unrestricted reader may retain a valid legacy Branch default or leave Branch blank.
- An authorised Branch is revalidated against Company→Branch setup before it is used.
- Default Warehouse resolution occurs only after an authorised Branch is known and continues through the existing Branch Profile/read-permission resolver.

## Read and option composition

- Page and export continue to reuse one bounded dataset builder.
- The hardened report authority continues to resolve exact Warehouse scope before Stock Ledger Entry reads.
- Restricted blank-Branch reads validate the selected Warehouse against the union of active permitted Branch Warehouses; restricted-zero remains fail-closed.
- Branch and Warehouse selectors continue through the bounded operational queries.
- Company, Item, UOM and Batch selectors remain permission-aware and bounded.
- The 1,000-row raw Stock Ledger cap remains enforced before display filtering.

## Safety boundaries

- ERPNext stock balance and Stock Ledger Entry remain the accounting/stock truth.
- Opening Stock Reconciliation, running balance, source/destination classification, UOM conversion, pagination and export semantics are unchanged.
- No Stock Entry, Stock Ledger Entry, Stock Reconciliation, Bin, Warehouse, Item or other document is mutated.
- No guided transfer, stock-posting or reporting feature is introduced.

## Manual QA checklist

1. Restricted single-Branch reader: context selects that Branch and only a readable configured default Warehouse.
2. Restricted multi-Branch reader with valid default: context preserves the authorised Branch and resolves its Warehouse.
3. Restricted multi-Branch reader with stale/no default: Branch and Warehouse remain blank until an authorised selection is made.
4. Restricted zero-active-Branch reader: Branch/Warehouse defaults and options expose no unauthorised scope; reads fail closed.
5. Unrestricted manager: valid legacy default remains usable and blank Branch retains established Company/Warehouse behavior.
6. Select a Warehouse outside the authorised Branch union and confirm page/export both reject it.
7. Compare page and export for identical filters and confirm rows, opening balance and summaries reconcile.
8. Confirm the 1,000-row cap still fails before display filters can hide excess raw rows.
9. Confirm movement types, Stock Reconciliation opening treatment and compare-UOM values remain unchanged.
10. Confirm no stock or accounting document is mutated by context, search, page or export reads.
