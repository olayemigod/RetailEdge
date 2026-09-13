# RIR2G2D — Responsive Table Reconciliation Contract

## Goal

Confirm that ordinary RetailEdge EdgeSuite table surfaces remain usable on narrow screens without hiding columns, clipping actions, or forcing the whole page/modal wider than its viewport.

This slice is a reconciliation and regression-hardening slice. It must not rewrite tables that are already responsive.

## Repository Evidence

### Shared EdgeSuite report tables

The governed EdgeSuite UI 1.1.0 candidate at `e40ea4d7dc000d17443a0571c1e246b61bfd3e1d` already owns responsive report-table presentation:

- `.edge-report-table-wrap { width:100%; overflow:auto; ... }`;
- `.edge-report-table { width:100%; min-width:max-content; ... }`.

Therefore RetailEdge EdgeReportShell / EdgeReportTable consumers must not receive product-local responsive-table rewrites.

### Frappe table-responsive contract

Frappe v16's shipped Bootstrap CSS defines:

- `.table-responsive { overflow-x:auto; }`;
- narrow-screen table cells remain nowrap inside the responsive container.

Professional Purchasing overlays that use `<div class="table-responsive">` therefore already have an authoritative horizontal-scroll container in the supported Frappe runtime.

### RetailEdge local raw tables

Repository audit found raw `<table>` markup only in a bounded set of RetailEdge Vue surfaces. Every one is already contained by one of:

- a component-local wrapper with `overflow:auto` or `overflow-x:auto`; or
- Frappe's `table-responsive` wrapper.

Representative local wrappers include:

- `assignment-table-wrap`;
- `table-wrap`;
- `customer-360-table-wrap`;
- `native-control-table-wrap`;
- `quality-table-wrap`;
- `period-table-wrap`;
- `profit-table-wrap`;
- `manager-table-wrap`;
- `movement-table-wrap`;
- `supplier-review-table-wrap`;
- `table-responsive`.

No current raw-table surface was found without horizontal overflow containment.

## Decision

**No runtime UI rewrite is required for RIR2G2D.**

The safe change is a regression contract test that inventories every RetailEdge Vue file containing raw table markup and requires each surface to remain inside an approved responsive wrapper.

This is preferable to:

- replacing operational/editable tables with report tables;
- hiding columns on mobile;
- duplicating shared EdgeSuite report CSS;
- changing Frappe Bootstrap utilities;
- adding card/mobile variants without a demonstrated usability defect.

## Contract

1. Every RetailEdge Vue file containing raw `<table>` markup must be explicitly inventoried.
2. Every inventoried raw-table surface must contain its approved responsive wrapper.
3. Component-local wrappers must continue to declare horizontal/automatic overflow.
4. `table-responsive` surfaces may rely on the supported Frappe v16 Bootstrap contract.
5. New raw-table surfaces must fail the contract test until their responsive behavior is explicitly classified.
6. EdgeReportShell / EdgeReportTable surfaces remain owned by the shared EdgeSuite runtime and are not product-patched here.
7. Responsive behavior must preserve columns, actions and document identity; do not silently remove information on narrow screens.

## Out of Scope

- sorting (frozen in G2C1/G2C2);
- table virtualization;
- column hiding or mobile card redesign;
- new pagination;
- shared EdgeSuite UI changes;
- Frappe/Bootstrap changes;
- loading/error/empty-state reconciliation;
- date-format reconciliation;
- Link-field cascade/filtering;
- browser/persona acceptance, which remains in consolidated RIR2E.

## Safety

RIR2G2D must not change:

- accounting, Payment Ledger, GL, Stock Ledger or valuation truth;
- document submit/cancel/amend lifecycle;
- roles, permissions or Branch scope;
- workflow semantics;
- backend report scope;
- `ignore_permissions` or transaction commits.

## Tests Required

- exact inventory of Vue files containing raw `<table>` markup;
- every inventoried file contains its approved wrapper marker;
- every component-local wrapper still declares `overflow:auto` or `overflow-x:auto`;
- no new raw-table file can appear without explicit responsive classification.

## Freeze Rule

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility all pass on one exact head.

## Next Audit Area

After RIR2G2D freezes, continue the existing Phase-3 reconciliation with loading, error and empty-state consistency.
