# RetailEdge Professional Selling Suite

## Goal

Provide one RetailEdge selling experience for Quotation → Sales Order → Delivery while preserving ERPNext as the authoritative source for pricing, taxes, stock, Shipping Rules, document workflow and accounting.

## Delivery bundle

This branch intentionally combines the former selling phases into one implementation unit:

1. Shared selling-document foundation
2. Professional Quotation
3. Professional Sales Order
4. Delivery and shipping charges

These stages share the same customer, item, pricing, Operating Context, Stock Location, Shipping Rule and document-conversion rules and should be reviewed together rather than as isolated PRs.

## First foundation slice

- New `professional-selling` EdgeSuite Page.
- Single-shell architecture: Frappe Page loader → `edgeui.bundle.js` → `professional_selling.bundle.js` → `EdgeAppShell` / `EdgePageLayout`.
- Shared server registry for Quotation, Sales Order and Delivery Note.
- Permission-aware capability detection.
- Operating Company/Branch context display.
- Effective selling Price List visibility using the existing RetailEdge pricing resolver.
- ERPNext Shipping Rule capability detection.
- Bounded recent-document list using `frappe.get_list`.
- Native ERPNext create/view fallback retained while the shared draft editors are implemented.

## Accounting, stock and shipping safety

- Submitted ERPNext documents must not be mutated.
- RetailEdge must not create a parallel sales ledger, delivery-charge ledger or shipping ledger.
- Selling Price Lists and Pricing Rules remain ERPNext truth.
- Delivery charges use ERPNext `Shipping Rule`, taxes and charges mechanisms where applicable.
- Sales Order and Delivery Note stock fields remain ERPNext Warehouse fields internally; customer-facing UI uses Stock Location terminology.
- Delivery fulfilment should preferentially map from submitted Sales Orders using ERPNext document-mapping behavior rather than copying rows independently.
- Draft creation must remain permission-aware and server validated.

## Planned next slices on this same branch

### Shared draft editor contract

- Customer and item Link searches: bounded, permission-aware and context filtered.
- Company / Branch / Stock Location cascading defaults.
- Server-authoritative Price List and item pricing.
- Shared item table behavior.
- Shipping Rule selection filtered to valid ERPNext Shipping Rules.
- Native full-form fallback for advanced fields.

### Quotation

- Customer quotation only for the first RetailEdge reference implementation.
- Transaction Date and Valid Till.
- Customer, items, quantities, rates, Shipping Rule and remarks/terms essentials.
- Save ERPNext Quotation draft only.

### Sales Order

- Customer, Transaction Date, Delivery Date, source Stock Location, items and Shipping Rule.
- Create from a submitted Quotation through ERPNext mapping where possible.
- Save ERPNext Sales Order draft only unless user explicitly submits through normal ERPNext workflow.

### Delivery

- Prefer creation from a submitted Sales Order using ERPNext mapping.
- Preserve delivered quantities, reserved/ordered quantities and stock validation.
- Source Stock Location and Shipping Rule remain ERPNext fields.
- No mutation of submitted Sales Orders.

## QA gates

- Unit/source contracts for permission, bounded queries and no accounting side effects.
- Clean Frappe v16 install/migrate/assets/full RetailEdge suite.
- EdgeSuite asset and Page governance.
- Browser QA for light/dark/mobile layout.
- Quote → Order → Delivery workflow QA with realistic customer/items.
- Shipping Rule calculation parity against native ERPNext.
- Branch/Stock Location and permission-isolation QA.
