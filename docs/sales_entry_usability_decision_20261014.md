# Sales entry usability decision

Date: 2026-10-14

## Baseline

RetailEdge remains on ERPNext/Frappe version 16. The current v16.50 baseline keeps Sales Invoice, Pricing Rule, Tax Category, Sales Taxes and Charges Template, workflow, permissions, accounting and stock posting authoritative.

The existing EdgeSuite UI runtime remains the shared UI layer. Its Link, Input, Dropdown, Modal and Child Table components continue to own field and responsive table behavior; RetailEdge does not fork those primitives.

## Research applied

ERPNext v16.50 preserves manually entered discounts when a draft Sales Invoice is recalculated while removing a stale transaction-level Pricing Rule discount that no longer applies. Current permission hardening also reinforces using native permission-aware lookups rather than alternate RetailEdge selectors.

Mature retail sale surfaces such as Shopify POS and Square keep the current sale/cart value visible while operators work, distinguish item-level adjustments from sale-wide adjustments, and progressively expose secondary commercial controls rather than putting every option in the primary entry path.

## Decision

For wide screens, Make Sale and Quick Sale use the existing entry work area as the primary column and keep the authoritative Sale Summary visible in a sticky secondary rail. The existing Discount & tax control remains progressive disclosure in the main entry flow. The existing sticky Make Sale action bar remains the save/update boundary.

Below the wide-screen breakpoint, both surfaces remain single-column. EdgeSuite Child Table continues to own table responsiveness and horizontal constraints.

The Tax Template help text is corrected to render business-facing guidance rather than a literal Vue expression. Normal user-facing guidance refers to automatic tax treatment rather than exposing implementation terminology.

## Deliberate non-changes

- No pricing, promotion, tax, accounting or stock calculation changes.
- No new RetailEdge table, modal, input, link or dropdown primitive.
- No Pricing Rule editor or manual tax-row editor.
- No submitted Sales Invoice mutation.
- No migration or schema change.
- No change to the Quick Sale line limit or Quick Sale → Make Sale handoff.

## Validation boundary

The slice must preserve the five canonical RetailEdge gates on one exact candidate: Linters, CI, RetailEdge Upgrade Validation, EdgeSuite UI Candidate Compatibility and RetailEdge Browser Persona Smoke.
