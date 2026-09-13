# RetailEdge B2B2A — Guided Purchase Order Draft

## Goal

Close the first confirmed Professional Purchasing workflow-completeness gap for `EdgeSuite Only` users: creating a normal Purchase Order must not require opening the native ERPNext Purchase Order form.

This slice makes the existing **New Purchase Order** action EdgeSuite-first. ERPNext remains the Purchase Order lifecycle and validation authority.

## User flow

From Professional Purchasing:

1. An authorised user selects **New Purchase Order**.
2. RetailEdge opens an EdgeSuite guided Purchase Order dialog instead of immediately calling `frappe.new_doc("Purchase Order")`.
3. The dialog loads the authenticated user's operating Company/Branch and preferred receiving Stock Location.
4. Supplier, Branch, Stock Location and Item selectors are permission-aware and context-filtered.
5. Buying rates are resolved from the authenticated user's Buying Price List, ERPNext buying-price rules and last-purchase information; the server resolves pricing again on save.
6. RetailEdge inserts one standard ERPNext **draft** Purchase Order.
7. The user remains in Professional Purchasing and the workspace refreshes.

`Native Desk + EdgeSuite` users retain an **Open Full Form** fallback from the guided dialog. The fallback is not shown to `EdgeSuite Only` users.

## Business fields in the guided slice

The bounded guided form includes:

- Operating Company
- Branch
- Supplier
- Order Date
- Required By date
- Receiving Stock Location
- Items
- Quantity
- Buying Rate
- Terms / Notes

It intentionally does not reproduce every advanced Purchase Order field. Complex taxes, subcontracting, advanced terms, specialised schedules and exceptional procurement cases remain ERPNext advanced workflows.

## Backend safety

`retailedge.professional_purchase_order` owns only the guided draft preparation contract.

It:

- requires current-user `create` permission on Purchase Order;
- reuses the established guided Purchase Invoice helpers for transaction context, branch/warehouse validation and item normalization;
- reuses `resolve_price_list_context(mode="buying")` and `resolve_purchase_item_pricing`;
- validates Supplier, Item, Company, Branch and Stock Location through current-user ERPNext/Frappe permissions;
- requires Required By date to be on or after Order Date;
- assigns Branch only through an existing Purchase Order branch field;
- inserts exactly one draft Purchase Order using normal ERPNext validation.

It does **not**:

- submit the Purchase Order;
- create Purchase Receipt or Purchase Invoice automatically;
- create Stock Ledger or GL entries;
- mutate submitted documents;
- use `ignore_permissions`;
- call `frappe.db.commit` or `frappe.db.set_value`;
- grant procurement rights to RetailEdge Manager or Branch Manager roles.

## Smart-form behaviour

The dialog follows ProcessEdge form rules:

- Supplier search is permission-aware.
- Item search is limited to enabled purchase items and respects Supplier context where ERPNext supports it.
- Branch search is limited to permitted branches for the Company.
- Stock Location search is Company/Branch-aware.
- Changing Branch clears and re-resolves the preferred receiving Stock Location.
- Selecting a Stock Location resolves/validates its Branch.
- Changing Supplier or Branch refreshes item buying rates.
- Server validation repeats all business-critical checks; frontend filtering is not the security boundary.

## UI integration

Professional Purchasing is a large existing EdgeSuite workspace. To avoid a risky wholesale rewrite, B2B2A adds a small product-local compiled overlay bundle and promotes the existing **New Purchase Order** button through a capture listener in the Page controller.

The existing Professional Purchasing Vue source is not rewritten. The original native button handler is prevented only for that exact button action and replaced with the guided overlay. This keeps the slice narrow and reversible while preserving the existing workspace.

## Explicitly out of scope for B2B2A

This checkpoint does not yet claim full EdgeSuite-only procurement completion.

Still classified for later bounded slices:

- RFQ draft post-create native review
- Purchase Receipt draft post-create native review
- Purchase Return native review
- Supplier Debit Note native review
- native Purchase Order row/list opens
- native Material Request / RFQ / Supplier Quotation lists and reports
- Landed Cost Voucher completion

Landed Cost Voucher is expected to remain an advanced native handoff because freight/customs/other charges and final valuation effects require full ERPNext stock/accounting review. EdgeSuite-only users should escalate that advanced action rather than bypass ERPNext controls.

## Validation required

Freeze only when the exact head passes:

1. RetailEdge Theme Compatibility
2. Linters / pre-commit / Semgrep / dependency audit
3. Clean Frappe v16 install + migrate + full RetailEdge tests
4. EdgeSuite UI Candidate Compatibility

No browser QA is claimed by this source checkpoint. Final persona QA must include an EdgeSuite-only Purchase User creating a draft Purchase Order, changing Branch/Stock Location, adding multiple items, checking price refresh, and confirming no native Desk redirect occurs after save.
