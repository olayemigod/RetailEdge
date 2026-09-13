# Pre-reporting Stock Movement Read Scope Contract

## Purpose

B4B1 aligns RetailEdge Stock Movement History and its Branch/Warehouse filter searches with the Branch Assignment-aware operating scope established in B3 and reused by B4A.

## Scope authority

Both the report resolver and stock-movement filter RPCs use `retailedge.operating_context.get_operational_branch_scope()`.

This preserves the established precedence:

- global RetailEdge branch-access users are unrestricted;
- when Branch Assignment history exists, active Branch Assignments are authoritative;
- without Branch Assignment history, the operating-scope helper retains the legacy User Permission/default/Branch Profile compatibility fallback.

A restricted user with zero active permitted Branches is never interpreted as unrestricted.

## Report rules

For Stock Movement History:

- Warehouse remains required and remains the exact Stock Ledger Entry scope used by the report;
- restricted + explicit Branch requires that Branch to be in the active permitted set;
- restricted + blank Branch validates the selected Warehouse against the union of Warehouses belonging to active permitted Branches;
- restricted + zero active Branches fails closed;
- Warehouse must still belong to the selected Company and must not be a group Warehouse;
- unrestricted + blank Branch preserves the existing company-Warehouse behaviour.

The ERPNext stock-balance API, Stock Ledger Entry rows, reconciliation handling, UOM conversion and running-balance semantics are unchanged.

## Filter-search rules

The shared `branch_query()` and `warehouse_query()` endpoints now use the same operating-scope contract:

- restricted Branch searches return only active permitted Branches;
- restricted Warehouse searches with blank Branch are limited to Warehouses across active permitted Branches;
- an explicitly supplied unauthorized Branch is rejected before Warehouse search;
- restricted users with zero active Branches receive no Branch/Warehouse options;
- unrestricted users retain existing permission-aware company-wide search behaviour.

These endpoints are shared by Stock Movement History and Stock Position filter controls, so the search surface now matches the B4A dataset boundary.

## Non-goals

B4B1 does not:

- alter stock posting, Stock Ledger Entry, GL or reconciliation truth;
- change submitted documents;
- change the global legacy `validate_user_branch_access()` compatibility helper;
- change Stock Movement report presentation or route promotion;
- broaden ERPNext DocType or Page permissions;
- introduce reporting-development features.
