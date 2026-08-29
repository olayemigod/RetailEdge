# E16 Competitive Gap Audit — ERPNext-first baseline

This audit is the implementation filter after the E15 multi-app coexistence checkpoint.

## Rules

1. ERPNext remains the source of truth for accounting, stock, selling, buying, projects and payment documents.
2. Do not rebuild native ERPNext capabilities. Add guided orchestration, controls, collaboration and reporting where the native experience has a real usability or market gap.
3. EdgeSuite UI remains the shared frontend runtime.
4. The product must remain safe alongside other Frappe/ERPNext product apps.
5. E16 remains stacked on the exact green E15 checkpoint `1f01b27d02b322f49ecaaecf1103a4b7188d6fed`; continue the existing E16 branch/PR rather than creating divergent implementation lines.

## Native ERPNext capabilities that are not gaps

- Payment Terms / Payment Terms Template already cover deposits, instalments, credit periods and milestone schedules.
- Payment Request already provides invoice/order payment requests and gateway links.
- Subscription and Auto Repeat already cover recurring/retainer billing patterns.
- Dunning already provides formal overdue collection notices, optional interest/fees and linked payment handling.
- ERPNext Customer Portal already exposes customer/order information and Project portal access can expose tasks/timesheets.
- ERPNext Supplier portal already exposes Request for Quotation, Supplier Quotation, Purchase Order and Purchase Invoice with Supplier ownership checks derived from Portal User links.

The product should expose or orchestrate these safely rather than create parallel ledgers or duplicate recurring-billing, buying or payment documents.

## Priority A — Customer collaboration and self-service — IMPLEMENTED / GREEN

The EdgeSuite customer portal now extends native ERPNext documents without mutating submitted accounting documents:
- quotation accept/decline and transaction-scoped collaboration are append-only;
- invoice payment initiation uses native ERPNext Payment Request and configured gateways;
- outstanding, overdue, received-payment, available-advance and receivable statement context remain native accounting read models;
- project progress and only explicitly customer-published Project Updates are exposed;
- customer/company/document identity is server-derived and revalidated;
- PDF access uses ERPNext website permission and server-controlled Print Format selection;
- no direct Payment Entry, GL Entry or Stock Ledger Entry writes are introduced by portal self-service.

Validated checkpoint: `273d795d4acd66b7478f8968a5a74ef40ff50681`
- RetailEdge Theme Compatibility #105: PASS
- Linters #1800: PASS
- CI #1818, including full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #56: PASS

## Priority A — Receivables automation workspace — IMPLEMENTED / GREEN

The collections workspace orchestrates ERPNext Accounts Receivable, Payment Terms, Payment Request and Dunning with:
- overdue prioritisation;
- reminder/dunning readiness;
- governed Payment Request and Dunning handoffs;
- existing Action Follow Up visibility for collection follow-up scheduling without misrepresenting follow-up notes as an accounting or customer promise-to-pay balance;
- branch/company/permission-aware collection queues.

The Action Follow Up store remains operational follow-up metadata, not a shadow receivables ledger.

Validated with the same Priority-A checkpoint `273d795d4acd66b7478f8968a5a74ef40ff50681`.

## Priority B — Supplier collaboration — NEXT

ERPNext v16 already owns Supplier portal transaction pages and website permissions for Request for Quotation, Supplier Quotation, Purchase Order and Purchase Invoice. RetailEdge must not rebuild them.

Implement an additive, product-neutral supplier workspace that reuses those native routes and Supplier ownership boundaries while adding genuine collaboration gaps:
- unified supplier dashboard over native RFQ, Supplier Quotation, Purchase Order and Purchase Invoice;
- purchase-order acknowledgement and supplier messages as append-only collaboration records, never Purchase Order mutation;
- read-only payment/payables/statement context derived from ERPNext accounting data;
- secure document/attachment intake routed to native buying documents with human review before any posting;
- strict Supplier Portal User ownership checks on every read/write boundary.

## Priority B — Project collaboration — PARTIALLY IMPLEMENTED / GREEN

Customer-facing project collaboration is now available through native Project progress plus explicitly published Project Updates. Internal Project/Task/Timesheet/Expense Claim and project-linked sales/purchase documents remain ERPNext authority. Further Project collaboration should be added only where a confirmed UX gap remains; do not duplicate project accounting.

## Priority C — Document capture assistance

Evaluate attachment/document intake and extraction assistance for supplier bills/receipts. Any accepted transaction must still be created and validated as the correct native ERPNext document, with human review before posting.

## Current execution order

1. Preserve Priority-A green checkpoint `273d795d4acd66b7478f8968a5a74ef40ff50681` as a reconcilable milestone.
2. Continue Priority-B Supplier Collaboration on the existing `agent/competitive-gap-nextgen-20260829` / PR #53 line.
3. Validate every Supplier slice at exact head before expanding to document capture assistance.
4. Keep manual QA deferred until implementation is complete and the cumulative E16 line is reconciled into the single consolidated QA branch.
