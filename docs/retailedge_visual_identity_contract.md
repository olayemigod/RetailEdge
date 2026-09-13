# RetailEdge Visual Identity Contract

## Goal

RetailEdge must remain an EdgeSuite UI product while being visually recognisable as a retail and business-operations application even when product names and logos are removed.

EdgeSuite UI owns reusable primitives, interaction behaviour, accessibility, responsive foundations, modal behaviour, shared reporting controls, and common runtime contracts.

RetailEdge owns product composition and visual identity.

## Governing rule

> EdgeSuite defines interaction consistency. RetailEdge defines retail identity and commercial composition.

RetailEdge must not copy or fork shared EdgeSuite components merely to look different.

## Shared EdgeSuite contracts retained

RetailEdge continues to use the shared runtime and components where applicable, including:

- EdgeAppShell
- EdgePageLayout
- EdgePageHeader
- EdgeFilterBar
- EdgeLinkField
- EdgeDataTable
- EdgeReportShell
- EdgeModal
- EdgeStatCard
- EdgeLoadingState
- EdgeEmptyState
- EdgeErrorState
- shared export and navigation infrastructure

ERPNext remains authoritative for accounting, stock, submitted documents, ledgers, and document workflow truth.

## RetailEdge-owned presentation

RetailEdge applies its own presentation only under the active RetailEdge product scope:

- `body.edge-suite-product-retailedge`
- `[data-edge-product="retailedge"]`

The product layer owns:

- dark operational sidebar treatment;
- retail-specific accent and surface tokens;
- denser operational spacing;
- commercial KPI hierarchy;
- compact filters and actions;
- ledger-like table readability;
- Business Hub command-centre composition;
- attention/exceptions emphasis;
- RetailEdge-specific dark-mode treatment;
- responsive adjustments appropriate for high-frequency business operations.

## Reference experience

The Business Hub is the reference RetailEdge composition.

Its visual hierarchy should prioritise:

1. active company and branch context;
2. today's sales/cash/business KPIs;
3. items needing attention;
4. quick operational actions;
5. stock, banking, branch, and cash-shift signals;
6. deeper operational and analytical navigation.

The intended mental model is:

`Sell -> Collect -> Stock -> Buy -> Spend -> Reconcile -> Review`

## Safety rules

This layer must not:

- change accounting calculations;
- mutate submitted ERPNext documents;
- change stock posting semantics;
- change branch or permission enforcement;
- change guided-entry business logic;
- copy EdgeAppShell or other EdgeSuite primitives into RetailEdge;
- style VetEdge, EduEdge, normal Frappe Desk, or other products;
- create a parallel report or navigation runtime.

## QA contract

Before promotion:

- confirm RetailEdge is visually distinguishable from VetEdge and EduEdge;
- verify light and dark mode;
- verify desktop, tablet, and mobile layouts;
- verify sidebar active/hover states;
- verify topbar context visibility;
- verify KPI readability with large Nigerian Naira values;
- verify dense tables remain horizontally usable;
- verify modals/dropdowns remain above product chrome;
- verify Business Hub, Owner Dashboard, Sales, Money, Stock, and Action Centre retain their existing operational behaviour.

## Rollout

Phase 1 is intentionally presentation-only:

- load the scoped RetailEdge identity stylesheet;
- establish Business Hub as the reference composition;
- add source-level regression coverage.

Further page-specific composition changes should be bounded QA corrections and must reuse the shared EdgeSuite primitives.
