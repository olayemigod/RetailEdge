# RIR2G2G27 — Basket & Product Affinity Date-Aware Customer/Salesperson Option Scope

## Goal

Complete the shared Sales reporting smart-form contract for Basket & Product Affinity by making its Customer and Salesperson selectors follow the active reporting period.

## Gap

Basket & Product Affinity already uses the shared G2G21 `search_sales_reporting_options` endpoint with Company, Branch and Item Group context.

The page also has From Date and To Date filters, but does not pass them into option search. Therefore Customer/Salesperson choices may include identities with no submitted sales evidence in the selected affinity period.

## Required contract

- Pass `from_date` and `to_date` from the active Basket Affinity filters into shared Sales reporting option search.
- Changing either date clears Customer and Salesperson because their validity is period-dependent.
- Company and Branch cascades remain unchanged.
- Item Group/Product Anchor behavior remains unchanged.
- Clearing Branch may retain Customer/Salesperson because Branch scope broadens.
- Continue using G2G21's shared backend option authority; do not add a Basket-specific Sales Invoice search engine.

## Out of scope

- Basket pair generation, support/confidence calculations, invoice/item scan limits, minimum-pair threshold, export or pagination.
- Item/Item Group option semantics.
- Native Item detail containment, which is already gated by Native Desk capability.
- Sales Invoice, accounting, stock or master mutations.

## Safety

- Frontend-only correction.
- No server API/schema change.
- No role/permission or Branch Assignment change.
- Shared EdgeSuite UI runtime remains unchanged.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
