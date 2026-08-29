# E16 Competitive Gap Audit — ERPNext-first baseline

This audit is the implementation filter after the E15 multi-app coexistence checkpoint.

## Rules

1. ERPNext remains the source of truth for accounting, stock, selling, buying, projects and payment documents.
2. Do not rebuild native ERPNext capabilities. Add guided orchestration, controls, collaboration and reporting where the native experience has a real usability or market gap.
3. EdgeSuite UI remains the shared frontend runtime.
4. The product must remain safe alongside other Frappe/ERPNext product apps.
5. Any new E16 implementation is stacked on the exact green E15 checkpoint `1f01b27d02b322f49ecaaecf1103a4b7188d6fed`.

## Native ERPNext capabilities that are not gaps

- Payment Terms / Payment Terms Template already cover deposits, instalments, credit periods and milestone schedules.
- Payment Request already provides invoice/order payment requests and gateway links.
- Subscription and Auto Repeat already cover recurring/retainer billing patterns.
- Dunning already provides formal overdue collection notices, optional interest/fees and linked payment handling.
- ERPNext Customer Portal already exposes customer/order information and Project portal access can expose tasks/timesheets.

The product should expose or orchestrate these safely rather than create parallel ledgers or duplicate recurring-billing documents.

## Confirmed experience gaps worth implementation

### Priority A — Customer collaboration and self-service

Extend the existing EdgeSuite customer portal around native ERPNext documents so customers can:
- view quotations and clearly accept/decline them without mutating submitted accounting documents;
- add transaction-scoped comments/communication;
- initiate permitted invoice payments through native Payment Request / configured gateways;
- see invoice outstanding status, advance/credit context and statements;
- see relevant project progress and approved customer-facing project activity.

### Priority A — Receivables automation workspace

Provide an EdgeSuite collections workspace over ERPNext Accounts Receivable, Payment Terms, Payment Request and Dunning:
- overdue prioritisation;
- reminder/dunning readiness;
- payment-request creation/handoff;
- promise/follow-up visibility where supported without inventing accounting balances;
- branch/permission-aware customer collections queues.

### Priority B — Supplier collaboration

Evaluate a supplier-facing portal over native Purchase Order, Purchase Invoice, Payment Entry and attachments:
- purchase-order visibility and acknowledgement;
- supplier document upload/intake routed to native buying documents;
- payment-status and statement visibility;
- comments/activity with strict supplier ownership checks.

### Priority B — Project collaboration

Expose native Project/Task/Timesheet/Expense Claim and project-linked sales/purchase documents through a coherent EdgeSuite collaboration surface rather than duplicating project accounting.

### Priority C — Document capture assistance

Evaluate attachment/document intake and extraction assistance for supplier bills/receipts. Any accepted transaction must still be created and validated as the correct native ERPNext document, with human review before posting.

## First implementation tranche

Start with Customer Collaboration + Receivables Automation because the existing customer portal, professional selling, Payment Request/payment infrastructure, advanced payments and project operations provide the highest reuse with the lowest accounting risk.
