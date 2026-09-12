# RIR2G2G12 — Forecasting and Planning Native Workflow Containment

## Goal

Keep forecasting, planning, scenario analysis and the EdgeSuite-owned Sales Forecast → Planning Workspace transition available while containing retained native Desk routes and direct Planning Scenario form actions for EdgeSuite-only users.

## Scope

- Sales Forecast
- Forecasting & Planning
- Planning Scenario create/open affordances
- Shell DocType/Report navigation on both pages

## Required contract

- Both pages read `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Sales Forecast retains its EdgeSuite transition to Forecasting & Planning for every authorised page user.
- Forecasting & Planning keeps scenario identity, loading, analysis and forecast-versus-actual results visible in EdgeSuite.
- Planning Scenario create/open actions are disabled and explicitly labelled as advanced when Native Desk is unavailable.
- Create/open handlers independently fail closed; UI state is not treated as the security boundary.
- Forecast calculations, plan assumptions, actuals, filters, exports and permissions remain unchanged.

## Safety

- No forecast, plan, cash, inventory, budget or scenario calculation changes.
- No Company/Branch scope, option-search, export, role or permission changes.
- No accounting, stock or business-document mutation.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
