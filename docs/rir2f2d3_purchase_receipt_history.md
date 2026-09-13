# RIR2F2D3 — EdgeSuite Purchase Receipt History

## Goal

Close the post-receipt read gap for ordinary RetailEdge purchasing users.

After RIR2F2D2, an EdgeSuite-only user can review and submit a standard Purchase Receipt, but the existing **Purchase Receipts** action still routes to the native ERPNext list and is therefore hidden by the EdgeSuite-only parity gate. RIR2F2D3 makes receipt history an EdgeSuite-owned read surface while keeping native form/list access explicitly advanced.

## Frozen parent

RIR2F2D2 was frozen green at:

`a1d73d16f358069c941d2b293791d446da4e847b`

Exact-head gates passed on that parent:

- RetailEdge Theme Compatibility #417
- Linters #2258
- CI #2276
- EdgeSuite UI Candidate Compatibility #514

## In scope

- Reclassify the existing Professional Purchasing **Purchase Receipts** action as **Receipt History**.
- Intercept both the raw and rewritten labels before the legacy Vue native-list handler can run.
- Open a dedicated EdgeSuite Purchase Receipt History overlay.
- Show a bounded list of submitted, non-return Purchase Receipts only.
- Use Company, Branch and Supplier filters.
- Cascade filter changes: changing Company clears Branch and Supplier; Branch/Supplier refresh the result set.
- Use the existing permission-aware Professional Purchasing link search API for Company, Branch and Supplier options.
- Sort receipt history by Receipt, Date, Supplier, Quantity and Status.
- Keep receipt names as plain EdgeSuite data, not disguised native links.
- For Native Desk-authorised users only, provide explicit **Advanced: Open in ERPNext** and **Advanced: Purchase Receipts in ERPNext** actions.

## Backend safety

The history endpoint:

- requires Purchase Receipt read permission;
- resolves Company/Branch through the existing RetailEdge operating-context and branch-scope contract;
- uses `_branch_scoped_filters()` so restricted users fail closed when receipt branch attribution cannot be safely resolved;
- uses `frappe.get_list()` for the parent Purchase Receipt query so Frappe permission conditions remain authoritative;
- filters to `docstatus = 1` and `is_return = 0`;
- optionally filters by a readable Supplier;
- caps results at 100 rows and defaults the overlay to 50;
- obtains source Purchase Order references only for the already permission-scoped parent receipt names;
- does not expose native routes in the returned data.

## Native Desk boundary

The shared EdgeSuite-only operational guard continues to block native Purchase Receipt form/list routes for restricted users.

For Native Desk-authorised users, the history overlay may expose explicit advanced actions:

- **Advanced: Open in ERPNext** for one receipt;
- **Advanced: Purchase Receipts in ERPNext** for the native list.

These actions are not rendered for EdgeSuite-only users.

## Existing receipt behavior preserved

RIR2F2D3 does not change:

- RIR2F2D1 non-persisting receipt preview;
- RIR2F2D2 standard receipt posting;
- the advanced draft handoff for complex receipt preparation;
- serial, batch, quality-inspection, rejected-quantity or subcontracting rules;
- ERPNext stock or accounting semantics.

## Out of scope

- Purchase Receipt editing inside history;
- cancellation, amendment or return actions;
- draft Purchase Receipt management;
- advanced serial/batch/inspection workflows;
- landed-cost workflow redesign;
- Purchase Invoice ownership;
- reporting development;
- RIR2F2E or later purchasing hardening.

## Required automated validation

On the final exact head:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 install, migrate, build and full RetailEdge test suite;
- EdgeSuite UI Candidate Compatibility;
- RIR2F2C historical native-safety regression;
- RIR2F2D1 preview regression;
- RIR2F2D2 posting regression;
- RIR2F2D3 receipt-history ownership contract.

## Required manual browser QA before final purchasing freeze

### EdgeSuite-only purchasing user

- **Purchase Receipts** resolves to **Receipt History**, never the native ERPNext list;
- an immediate click during page mount also opens EdgeSuite history, not native Desk;
- history defaults to the permitted operating Company/Branch;
- Company change clears Branch and Supplier;
- Branch and Supplier searches show only valid options for the selected context;
- submitted non-return receipts display correctly;
- Receipt, Date, Supplier, Qty and Status sorting works;
- receipt numbers are not native links;
- no advanced native form/list buttons are visible;
- direct native Purchase Receipt routes remain blocked.

### Native Desk-authorised user

- EdgeSuite Receipt History remains the primary read surface;
- explicit advanced row/list actions open native ERPNext correctly;
- standard D2 receipt posting still returns to refreshed purchasing state.

### Safety

- restricted user cannot read another branch's receipts;
- blank-branch receipt history fails closed where the branch-scope contract requires attribution;
- supplier filtering does not reveal unpermitted receipts;
- result cap is enforced server-side;
- representative light/dark rendering is clean;
- browser console/network shows no new application errors.

## Freeze rule

RIR2F2D3 is not frozen until all required exact-head automated gates are green. Repository validation does not substitute for manual persona/browser QA.

Reporting remains blocked, and PR #55 remains the authoritative draft/unmerged reconciliation line.
