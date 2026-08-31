# E16 C16A — Pricing & Promotions Discoverability

## Goal

Expose ERPNext-native pricing and promotion configuration in RetailEdge EdgeSuite navigation without creating a parallel pricing, discount, coupon, campaign, or promotion engine.

## Context

RetailEdge Professional Selling already resolves item pricing through ERPNext `get_item_details`; ERPNext therefore remains authoritative for Price Lists, Item Prices and Pricing Rules. POSNext documents support for promotions, coupon codes, multiple price lists, customer-group offers, bulk pricing and other dynamic pricing behaviour. RetailEdge currently hides the native configuration surfaces required to manage those capabilities.

## Scope

Add one permission-aware `Pricing & Promotions` navigation group containing only native ERPNext DocTypes:

- `Price List`
- `Item Price`
- `Pricing Rule`
- `Promotional Scheme`
- `Coupon Code`

Each destination must continue through RetailEdge's existing DocType existence + native `read` permission gate. The group should disappear when none of its destinations are readable.

## Out of Scope

- custom RetailEdge pricing or promotion calculations;
- copying Pricing Rule logic;
- custom coupon validation or usage counters;
- loyalty/rewards implementation;
- POSNext source changes;
- automatic creation, mutation, enable/disable or submission of pricing records;
- branch-specific shadow pricing masters;
- changing ERPNext permissions or adding broader RetailEdge roles.

## Native Authority

ERPNext v16 remains authoritative for:

- Price List setup and currency/buying/selling flags;
- Item Price rates, UOM, validity, customer/supplier and batch context;
- Pricing Rule conditions, priorities, quantity/amount thresholds, customer/supplier targeting, free-item and discount behaviour;
- Promotional Scheme generation/management of pricing-rule structures;
- Coupon Code validity, usage and Pricing Rule linkage;
- final transaction price/discount calculation.

RetailEdge guided pricing must continue to consume ERPNext's pricing result rather than calculate an independent effective price.

## Permission Safety

Do not hard-code broader roles. Existing `_can_open_target` DocType handling must determine visibility using native DocType existence and `read` permission.

This intentionally allows ERPNext's own role model to differentiate:

- users who may only read Price Lists;
- Sales/Purchase Master Managers who may maintain Item Prices;
- Sales/Purchase/Accounts/System/Website managers who may maintain Pricing Rules or related promotion records according to ERPNext's own permissions.

## UI / Architecture

- No new page or dialog.
- No new frontend runtime.
- Add only a compact native navigation group in `NAVIGATION_GROUPS`.
- Keep target uniqueness across business groups.
- Preserve EdgeSuite Business Hub/waffle navigation architecture.

## Tests Required

Focused contract coverage must verify:

1. exactly one `pricing-promotions` group exists;
2. it contains the five approved native DocType targets in the approved order;
3. no duplicate target is introduced elsewhere;
4. DocType navigation continues through `_has_permission_cached(..., "read", ...)`;
5. no custom pricing/promotion service, ledger, write API or legacy Frappe dialog is introduced;
6. the approved business-navigation architecture test includes the new group.

## Validation Gate

Freeze the exact candidate head and require:

- RetailEdge Theme Compatibility;
- Linters including pre-commit, Semgrep and dependency audit;
- clean Frappe v16 standalone CI with full RetailEdge tests;
- governed EdgeSuite UI Candidate Compatibility with full RetailEdge tests.

Manual QA remains deferred until the cumulative implementation line is reconciled into the consolidated QA branch.
