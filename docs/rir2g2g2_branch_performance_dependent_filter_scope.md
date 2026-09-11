# RIR2G2G2 — Branch Performance Dependent Filter Scope Reconciliation

## Goal

Make Branch Performance Company → Branch → POS Profile → Cashier filters context-aware, permission-aware and resistant to stale dependent values without changing report calculations.

## Current gap

- Company changes clear Branch and POS Profile but can retain a Cashier selected under the previous Company.
- Branch changes can retain a POS Profile and Cashier selected under the previous Branch.
- POS Profile changes can retain a Cashier that is not assigned to that profile.
- The option endpoint receives Company only, so POS Profile and Cashier suggestions are not narrowed by the selected Branch/POS context.

## Required contract

- Company change clears Branch, POS Profile and Cashier.
- Branch select/clear clears POS Profile and Cashier.
- POS Profile select/clear clears Cashier.
- Branch drill-down/focus clears POS Profile and Cashier before reloading.
- The option API receives Company, Branch and POS Profile context.
- Explicit Branch is revalidated server-side through the governed operational Branch contract.
- Restricted-zero Branch access returns no POS Profile/Cashier options.
- Restricted users only see POS Profiles associated with permitted Branches.
- Branch Setup Company↔Branch mapping and configured default POS Profile remain authoritative RetailEdge signals.
- A POS Profile's own branch attribution may supplement the Branch Setup default mapping.
- Cashier choices are limited to configured Branch cashiers and explicit POS Profile users; do not load every enabled User.
- All option searches remain bounded and permission-aware.

## Safety rules

- No Branch Performance calculation, SQL aggregation or accounting truth changes.
- No Branch Assignment precedence changes.
- No schema migration.
- No submitted-document mutation.
- No permission broadening or ignore_permissions.
- No shared EdgeSuite UI runtime change.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
