# Pre-reporting Stock Read Branch Scope Contract

## Purpose

B4A hardens RetailEdge current-stock reads before reporting development. Stock Position is the shared current-stock dataset boundary used directly by Stock Position and indirectly by Inventory Intelligence.

## Authoritative branch scope

The read boundary reuses `retailedge.operating_context.get_operational_branch_scope()` so Branch Assignment history keeps the same precedence established by B3:

- users with global RetailEdge branch access remain unrestricted;
- when Branch Assignment history exists, active Branch Assignments are authoritative;
- where no Branch Assignment history exists, legacy User Permission/default/Branch Profile behaviour remains the compatibility fallback.

An empty allowed-branch list for a restricted user is not interpreted as unrestricted.

## Stock Position rules

For a restricted user:

- an explicitly requested Branch must be in the active permitted Branch set;
- a blank Branch aggregates Warehouses only across the active permitted Branch set;
- zero active permitted Branches fails closed;
- an explicitly requested Warehouse is revalidated against Company and permitted Branch scope;
- Warehouse-to-Branch resolution is interpreted from the resolver payload and cannot bypass Branch Assignment scope;
- ERPNext Warehouse read permissions are still applied after RetailEdge Branch scope is calculated.

For an unrestricted user, blank Branch preserves the existing company-wide Warehouse scope.

## Inherited surfaces

Inventory Intelligence composes its current-stock foundation through `_build_stock_position_dataset()`, so the same Warehouse scope applies to its Stock Position-derived rows, summaries and exports.

## Non-goals

B4A does not:

- change ERPNext stock, Bin, reorder, GL or SLE truth;
- change document submission or posting behaviour;
- alter the global legacy `validate_user_branch_access()` compatibility contract;
- broaden Page/DocType permissions;
- change Stock Movement History or unrelated reporting services;
- remove existing scan, pagination or Warehouse-count limits.

Further read services remain separate B4 audit slices and must be proven against the same restricted/unrestricted contract before pre-reporting hardening is considered complete.
