# RetailEdge Pre-Reporting EdgeSuite Operational Surfaces

## Purpose

This checkpoint characterizes the existing EdgeSuite-first operational routing before any further pre-reporting behavior changes.

The goal is to reuse and govern existing RetailEdge workspaces rather than create duplicate sales, purchasing, payment, or stock workflows.

## Authoritative runtime layer

`retailedge.edgesuite_ui.get_retailedge_business_hub_context` builds the permission-aware base navigation.

`retailedge.master_experience.get_retailedge_business_hub_context` is the hooked final Business Hub context and promotes already-built RetailEdge operational Pages only when the current user can open those Pages.

The final runtime therefore intentionally differs from the static base registry: the base retains native ERPNext destinations as advanced fallbacks, while the master-experience layer promotes product-owned EdgeSuite operational surfaces.

## Existing promoted everyday surfaces

### Selling

`professional-selling` is promoted into Sell when its Page permission passes. It provides the RetailEdge guided selling workspace for Quotations, Sales Orders, Delivery Notes and Sales Invoices while ERPNext remains the document and accounting authority.

### Purchasing

`professional-purchasing` is promoted into Buy when its Page permission passes. Its Page roles remain Purchase/Accounts/System Manager oriented; this checkpoint deliberately does not add RetailEdge product roles merely to make the page visible. Product-role visibility must never broaden underlying purchasing authority.

### Money

`payment-management` is promoted before the native Payment Entry fallback when its Page permission passes. It covers customer advances and invoice settlement using ERPNext Payment Entry and Payment Reconciliation truth.

## Deliberate non-promotion

`stock-movement-history` already exists as an EdgeSuite Page, but normal navigation still uses the `RetailEdge Stock Movement History` Query Report. This remains deliberate until the separate parity/export/mobile/browser acceptance gate is completed.

This checkpoint does not claim that browser QA is complete and does not promote that route prematurely.

## EdgeSuite-only follow-up

Promotion is not the end of the access audit. The promoted pages themselves must also avoid offering actions that require native Desk to an `EdgeSuite Only` user.

The next bounded slice must review page-local native affordances such as:

- native View/Open Records buttons;
- direct Form/List route opens;
- auto-opening native forms after a guided draft is created;
- native-only fallback buttons inside guided dialogs;
- advanced purchasing handoffs that cannot be completed inside EdgeSuite.

Advanced users with `Native Desk + EdgeSuite` may retain these handoffs where appropriate.

## Safety rules

- Do not change submitted accounting or stock documents.
- Do not create a parallel receivables, payables, stock, pricing, or reconciliation ledger.
- Do not add RetailEdge roles to ERPNext purchasing/accounting authority merely for UI convenience.
- Keep Frappe Page permissions and normal ERPNext permissions authoritative.
- Keep the shared EdgeSuite Desk Access selector as interface exposure only.
- Reuse existing RetailEdge Pages and backend services before creating new workflows.

## Validation contract

Focused tests freeze that:

- Professional Selling is promoted when permitted.
- Professional Purchasing is promoted before the native Purchase Order fallback when permitted.
- Payment Management is promoted before native Payment Entry when permitted.
- promoted Pages are standard and role-restricted.
- Professional Purchasing does not gain RetailEdge Manager/Branch Manager roles in this slice.
- Stock Movement History remains on the legacy Query Report pending its separate acceptance gate.
