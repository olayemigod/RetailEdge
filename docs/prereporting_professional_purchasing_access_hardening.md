# RetailEdge B2B2B — Professional Purchasing EdgeSuite-Only Handoff Hardening

## Goal

Keep Professional Purchasing usable and understandable for `EdgeSuite Only` operators without weakening ERPNext/Frappe permissions or pretending that advanced native purchasing, stock, quality, landed-cost, or supplier-governance forms have been rebuilt inside RetailEdge.

This slice follows the frozen B2B2A guided Purchase Order work. It is routing/presentation hardening only.

## Business rule

Professional Purchasing contains two kinds of actions:

1. **Saved-draft guided actions** — RetailEdge can safely prepare a standard ERPNext draft, persist it with the current user's normal permissions, and keep the restricted user on the EdgeSuite page. An authorised advanced user may later complete the native review/submission when required.
2. **Unsaved native-only continuation** — the action is not meaningful unless the user immediately enters an ERPNext native form. These controls must not be offered to `EdgeSuite Only` users.

The distinction is intentional. RetailEdge does not grant advanced native Desk exposure merely because a user can prepare a draft.

## Saved-draft guided actions preserved

The existing Professional Purchasing runtime remains authoritative for these prepared drafts:

- Request for Quotation from a submitted Purchase Material Request;
- Purchase Receipt from a submitted Purchase Order;
- Purchase Receipt return from a submitted Purchase Receipt;
- Supplier Debit Note from a submitted Purchase Invoice;
- Incoming Quality Inspection draft creation;
- guided Purchase Order creation from B2B2A.

For `EdgeSuite Only` users, automatic native Form redirects are blocked by the shared operational guard. The draft remains saved in ERPNext and can be continued by an authorised advanced user when the workflow genuinely requires native review.

No submitted source document is mutated by this presentation hardening.

## Native-only operations hidden or blocked

While the current Frappe route is exactly `professional-purchasing` and the shared boot mode is `edgesuite_only`, RetailEdge now treats these as advanced native handoffs:

### Native DocTypes

- Material Request
- Request for Quotation
- Supplier Quotation
- Purchase Order
- Purchase Receipt
- Purchase Invoice
- Landed Cost Voucher
- Quality Inspection
- Supplier Scorecard

### Native reports

- Supplier Quotation Comparison
- Purchase Order Analysis
- Procurement Tracker

Direct Form/List/report routing and matching `/app/...` / query-report URLs are blocked only on the configured EdgeSuite page.

### Native-only presentation controls

The restricted presentation removes native list/report buttons and record-open controls while preserving the EdgeSuite operational data already displayed on the page.

The entire Landed Cost panel is hidden for `EdgeSuite Only` users because the current guided landed-cost action returns an **unsaved** ERPNext Landed Cost Voucher that must immediately be completed on the native form. Hiding the operation is safer than leaving an unusable unsaved document in the browser model.

Created Quality Inspection drafts may still be prepared, but their native document-link buttons are hidden. The saved drafts remain available for authorised advanced review.

Supplier Scorecard summary/governance information remains visible because it is read-only and useful for purchasing decisions; only native Scorecard list/create/open controls are hidden.

## Shared guard extension

`retailedge_edgesuite_only_operational_guard.bundle.js` is extended in a backward-compatible way with:

- `nativeReports` for configured `query-report` routes and matching query-report URLs;
- `hiddenSelectors` for bounded native-only sections that should not be exposed to restricted users.

Existing Professional Selling and Payment Management configurations continue to work without supplying either option.

The guard still:

- activates only when `frappe.boot.edgesuite_ui_access.mode == "edgesuite_only"`;
- activates only on the exact configured current Frappe Page route;
- restores original hidden/disabled state when the user navigates away;
- leaves Native Desk + EdgeSuite users unchanged;
- does not alter ERPNext/Frappe permissions.

## Out of scope

This slice does **not**:

- implement a parallel RFQ editor or supplier communication engine;
- implement Purchase Receipt submission inside RetailEdge;
- implement Quality Inspection readings/acceptance/submission;
- implement Landed Cost Voucher charges, valuation allocation, or submission;
- implement Supplier Scorecard configuration;
- auto-submit Purchase Orders, RFQs, Purchase Receipts, Purchase Invoices, returns, debit notes, inspections, or landed-cost documents;
- write GL, Stock Ledger, Payment Ledger, or valuation entries;
- use `ignore_permissions` or manual database commits;
- broaden Purchase/Accounts/System Manager roles or Page permissions.

## Accounting and stock safety

ERPNext remains authoritative for:

- Purchase Order lifecycle and supplier controls;
- receipt quantities, warehouses, serial/batch requirements, stock posting and valuation;
- Purchase Invoice / Debit Note taxes and accounting;
- return stock effects;
- Quality Inspection requirements, readings and acceptance;
- Landed Cost Voucher allocation and stock valuation effects;
- Supplier Scorecard standing and governance enforcement.

Submitted accounting and stock documents are never mutated by this slice.

## Validation required

Freeze only after all four exact-head gates succeed:

1. RetailEdge Theme Compatibility
2. Linters / pre-commit / Semgrep / dependency audit
3. Clean Frappe v16 install + migrate + full RetailEdge test suite
4. EdgeSuite UI Candidate Compatibility

Focused contracts verify:

- report-route support remains bounded to configured reports;
- hidden-section state is reversible;
- Professional Purchasing loads the guard before its runtime bundles;
- native purchasing/quality/scorecard targets are explicitly configured;
- Landed Cost and created native inspection links are suppressed for restricted users;
- the B2B2A guided Purchase Order trigger remains in place;
- no backend transaction or permission logic was moved into the Page controller.

## Manual QA deferred

Final persona/browser QA should confirm at minimum:

- EdgeSuite-only purchasing user can prepare a Purchase Order draft without entering native Desk;
- RFQ/receipt/return/debit-note draft preparation remains on Professional Purchasing after successful save;
- Landed Cost is not offered to EdgeSuite-only users;
- Quality Inspection drafts can be prepared without exposing native links;
- Supplier Scorecard summary remains visible while native configuration links are absent;
- native Desk users retain all existing native list/report/form handoffs;
- leaving Professional Purchasing restores any controls hidden or disabled by the guard.
