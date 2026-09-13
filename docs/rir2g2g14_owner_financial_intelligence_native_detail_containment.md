# RIR2G2G14 — Owner and Financial Intelligence Native Detail Containment

## Goal

Keep owner and financial intelligence navigation inside RetailEdge while containing retained native DocType, Report and Sales Invoice detail routes for EdgeSuite-only users.

## Scope

- Owner Dashboard
- Money Overview
- 13-Week Cash Commitments
- Profitability Intelligence
- Profitability margin-evidence Sales Invoice drill-through

## Required contract

- All four pages read `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Owner Dashboard and Money Overview section and attention routes remain available because they target RetailEdge EdgeSuite pages.
- Profitability margin evidence and Sales Invoice identity remain visible.
- The native Sales Invoice action is included only for Native Desk users and its handler independently fails closed.
- Dashboard calculations, financial truth, filters, exports, printing, scope and cost visibility remain unchanged.

## Safety

- No profitability, cash, receivable, payable, stock, expense or owner-dashboard calculation changes.
- No Company/Branch scope, export, print, role or permission changes.
- No business-document mutation or shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
