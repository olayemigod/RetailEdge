# RetailEdge Pre-Reporting EdgeSuite Operational Surfaces

## Purpose

This checkpoint characterizes the existing EdgeSuite-first operational routing before any further pre-reporting behavior changes.

The goal is to reuse and govern existing RetailEdge workspaces rather than create duplicate sales, purchasing, payment, or stock workflows.

RIR2F1 now strengthens this contract for Selling: where the Professional Selling Page is permission-available, it is the canonical everyday RetailEdge owner of Sales Invoice, Sales Order and Delivery Note navigation rather than an additive peer beside native ERPNext routes.

## Authoritative runtime layer

`retailedge.edgesuite_ui.get_retailedge_business_hub_context` builds the permission-aware base navigation.

`retailedge.master_experience.get_retailedge_business_hub_context` is the hooked final Business Hub context and promotes already-built RetailEdge operational Pages only when the current user can open those Pages.

The final runtime intentionally differs from the static base registry. The base may retain native ERPNext destinations as compatibility/advanced fallbacks; the master-experience layer owns final product composition.

## Existing promoted everyday surfaces

### Selling — RIR2F1 contract

`professional-selling` is the canonical everyday RetailEdge selling workspace when its Page permission passes. It owns the normal RetailEdge journey for Quotations, Sales Orders, Delivery Notes and Sales Invoices while ERPNext remains the document, accounting, pricing, tax, stock and submission authority.

When Professional Selling is available:

- `Sales Invoice`, `Sales Order` and `Delivery Note` are removed as peer everyday navigation items from the final Sell group;
- Transaction Workspace, POS runtime and other permitted selling-management/configuration items remain;
- ordinary Professional Selling record browsing stays inside EdgeSuite through its Recent view;
- guided save handlers stay on Professional Selling instead of automatically opening native forms;
- explicit `Advanced: Open in ERPNext` actions are shown only when the shared EdgeSuite access context allows Native Desk;
- the existing EdgeSuite-only operational guard remains defence-in-depth.

When Professional Selling is not available or not permitted, existing native selling routes remain as permission-safe compatibility fallback so an authorised user is not stranded.

See `docs/rir2f1_selling_edgesuite_ownership.md` for the bounded implementation and QA contract.

### Purchasing

`professional-purchasing` is promoted into Buy when its Page permission passes. Its Page roles remain Purchase/Accounts/System Manager oriented; this checkpoint deliberately does not add RetailEdge product roles merely to make the page visible. Product-role visibility must never broaden underlying purchasing authority.

Purchasing remains additive in this checkpoint. RIR2F1 does not change Purchase Invoice, Purchase Order or Purchase Receipt ownership.

### Money

`payment-management` is promoted before the native Payment Entry fallback when its Page permission passes. It covers customer advances and invoice settlement using ERPNext Payment Entry and Payment Reconciliation truth.

Payment ownership is unchanged by RIR2F1.

## Deliberate non-promotion

`stock-movement-history` already exists as an EdgeSuite Page, but normal navigation still uses the `RetailEdge Stock Movement History` Query Report. This remains deliberate until the separate parity/export/mobile/browser acceptance gate is completed.

This checkpoint does not claim that browser QA is complete and does not promote that route prematurely.

## Remaining EdgeSuite ownership follow-up

RIR2F1 resolves the bounded Selling ownership leakage. Similar ownership decisions remain to be completed separately for:

- Professional Purchasing and purchase-document peer routes;
- Payment Management and normal payment read/management flows;
- stock receipt/count/transfer/read ownership;
- customer/supplier operational ownership;
- final Business Hub MVP composition.

Do not broaden RIR2F1 into those areas.

## Safety rules

- Do not change submitted accounting or stock documents.
- Do not create a parallel receivables, payables, stock, pricing, or reconciliation ledger.
- Do not add RetailEdge roles to ERPNext purchasing/accounting authority merely for UI convenience.
- Keep Frappe Page permissions and normal ERPNext permissions authoritative.
- Keep the shared EdgeSuite Desk Access selector as interface exposure only.
- Reuse existing RetailEdge Pages and backend services before creating new workflows.
- Native Desk availability does not make native ERPNext a peer everyday RetailEdge route.

## Validation contract

Focused tests freeze that:

- Professional Selling replaces Sales Invoice, Sales Order and Delivery Note peer navigation when permitted.
- Native selling peers remain when Professional Selling is unavailable/not permitted.
- Transaction Workspace, POS and unrelated selling-management entries remain intact.
- Professional Selling does not automatically eject guided saves or recent-record clicks into native ERPNext.
- explicit advanced native actions depend on `can_use_native_desk`.
- Transaction Workspace Sales Invoice read/manage routes to Professional Selling.
- Professional Purchasing is still promoted before the native Purchase Order fallback and is otherwise unchanged.
- Payment Management remains unchanged.
- promoted Pages are standard and role-restricted.
- Professional Purchasing does not gain RetailEdge Manager/Branch Manager roles in this slice.
- Stock Movement History remains on the legacy Query Report pending its separate acceptance gate.
