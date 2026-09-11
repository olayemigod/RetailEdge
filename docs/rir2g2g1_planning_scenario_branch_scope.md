# RIR2G2G1 — Planning Scenario Branch-Scope Reconciliation

## Goal

Make Forecasting & Planning scenario search/load/write/performance use the frozen RetailEdge operational Branch contract and remove direct client reads that can expose scenario data before Branch Assignment scope is validated.

## Current gap

- `planning_scope.py` still uses legacy branch helpers directly.
- Forecasting & Planning searches Planning Scenarios with `frappe.client.get_list` filtered only by Company.
- Scenario load uses `frappe.client.get`, returning the document before RetailEdge operational Branch scope is revalidated.
- Scenario validation and performance later validate scope, but that is too late for option-search/read confidentiality.

## Required contract

### Planning Branch resolution

- Delegate to `retailedge.operating_context.resolve_operational_branch`.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the legacy compatibility fallback already encapsulated by Operating Context.
- Unrestricted users may use blank Branch for company-wide planning.
- Restricted blank Branch with one permitted Branch resolves automatically.
- Restricted blank Branch with multiple permitted Branches requires explicit Branch for planning calculations/writes.
- Restricted-zero fails closed.

### Scenario option search

- Replace page-side `frappe.client.get_list` with a RetailEdge whitelisted endpoint.
- Search is permission-aware, bounded to 20 and requires a readable Company.
- Explicit Branch is revalidated server-side and only scenarios for that Branch are returned.
- Restricted blank-Branch search returns only scenarios in currently permitted active Branches so users can choose a saved scenario.
- Restricted-zero returns no options.
- Company-wide scenarios are not exposed to Branch-restricted users.
- Unrestricted blank-Branch search may return permitted scenarios across the selected Company.

### Scenario load

- Replace page-side `frappe.client.get` with a RetailEdge whitelisted endpoint.
- Native Planning Scenario read permission remains required.
- Stored Company/Branch is revalidated through the authoritative planning resolver before any payload is returned.
- Return only fields required by the EdgeSuite planning page.
- Do not expose the hidden immutable snapshot payload through the page endpoint.

## Safety rules

- No forecast, planning, stock, cash or accounting calculation changes.
- No schema migration or submitted-document mutation.
- No permission broadening.
- No `ignore_permissions`, `frappe.get_all` or manual DB commit.
- No shared EdgeSuite UI runtime changes.
- Do not reopen frozen G2A–G2F3 contracts.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.