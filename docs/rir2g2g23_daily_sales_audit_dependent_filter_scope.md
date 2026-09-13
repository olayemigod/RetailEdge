# RIR2G2G23 — Daily Sales Audit Dependent POS Profile and Cashier Scope

## Goal

Make the active Daily Sales Audit EdgeSuite page enforce a context-aware Company → Branch → POS Profile → Cashier selector cascade without changing the audit engine, audit workflow, report dataset, reconciliation logic, or ERPNext/POS truth.

## Gap

The active Daily Sales Audit page currently sends only Company to option search.

Consequences:
- POS Profile search is Company-scoped but not Branch-scoped.
- Cashier search reads every enabled permission-visible User instead of valid cashiers for the selected operational Branch/POS Profile.
- Company or Branch changes can leave stale POS Profile/Cashier selections.
- POS Profile changes do not clear a Cashier that may no longer be valid.

The underlying Daily Sales Audit dataset already uses its governed Company/Branch filters. This slice fixes form guidance and option scope only.

## Required contract

### Scope authority
- Reuse the existing RetailEdge operational Branch authority and Branch/POS scope logic already proven by Branch Performance.
- Do not introduce a second Branch Assignment or POS Profile ownership model.
- Restricted-zero branch scope returns no POS Profile or Cashier options.
- Explicit Branch outside current operational access fails closed through the existing branch validation path.

### POS Profile
- Options are limited to the selected Company and selected/permitted Branch scope.
- Existing RetailEdge Branch Setup default POS Profile mapping and POS Profile Branch attribution remain the accepted scope signals.
- Search remains bounded.

### Cashier
- Options are limited to configured Branch cashiers and explicit POS Profile users already used by Branch Performance.
- When a POS Profile is selected, Cashier options are restricted to that valid profile plus configured Branch cashiers under the same Branch scope.
- Only enabled permission-visible Users are returned.
- Search remains bounded.

### Frontend cascade
- Option requests pass Company, Branch and POS Profile.
- Selecting a new Company clears Branch, POS Profile and Cashier.
- Selecting a new Branch clears POS Profile and Cashier.
- Clearing Branch clears POS Profile and Cashier because the selected profile/cashier may not remain valid under broadened scope.
- Selecting or clearing POS Profile clears Cashier.
- Cashier selected label is cleared whenever Cashier is cleared.

## Out of scope

- Daily Sales Audit data calculations, variance logic, workflow states, review/approval, sorting, pagination, export, native detail containment, or report provider behavior.
- POS Profile/Branch Setup schema changes.
- Cashier Expense behavior.
- New roles, permissions, Branch Assignment rules, or accounting/stock writes.

## Safety

- No submitted document mutation.
- No `ignore_permissions`.
- No manual database commit.
- No broad User preload.
- Existing ERPNext/Frappe permissions remain authoritative.
- Shared EdgeSuite UI runtime remains unchanged.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Tests

- Daily Sales Audit option search delegates POS Profile and Cashier scope to the existing Branch Performance scope helpers.
- Company/Branch/POS Profile context is passed from the active Vue page.
- Company/Branch changes clear stale POS Profile/Cashier.
- POS Profile select/clear clears Cashier.
- Restricted-zero and invalid Branch behavior remains inherited from the existing operational scope helper.
- Daily Sales Audit dataset/report code is unchanged.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
