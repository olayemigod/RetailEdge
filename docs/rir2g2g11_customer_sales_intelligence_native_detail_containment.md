# RIR2G2G11 — Customer and Sales Intelligence Native Detail Containment

## Goal

Keep customer and sales intelligence fully readable and preserve EdgeSuite-owned Customer 360 transitions while containing direct native Customer, Item and Sales Invoice drill-through for EdgeSuite-only users.

## Scope

- Customer 360
- Customer & Sales Intelligence
- Customer Retention & Opportunity Intelligence
- Basket & Product Affinity
- Discount & Sales Quality

## Required contract

- Every page reads `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Customer & Sales Intelligence and Opportunity Intelligence retain clickable transitions to the EdgeSuite Customer 360 Page.
- Customer 360 keeps Customer, Item and Sales Invoice identity visible but exposes direct native form actions only to authorised Native Desk users.
- Basket Affinity and Sales Quality mark native detail columns clickable only when Native Desk is available and their handlers fail closed.
- All analytics, filters, export and cost-visibility behavior remains unchanged.

## Safety

- No sales, receivable, profitability, basket, discount or opportunity calculation changes.
- No Company/Branch scope, option-search, export, role or permission changes.
- No business-document mutation.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
