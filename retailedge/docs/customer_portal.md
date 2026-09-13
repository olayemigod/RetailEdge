# Customer Portal

## Purpose

Customer Portal provides an authenticated, customer-scoped website experience over ERPNext commercial documents. It does not create a second customer master, authentication system, receivables ledger, payment wallet, project ledger, or document store.

## Customer identity and access

- Users must be authenticated Website Users with the `Customer` role.
- Allowed Customer records are derived server-side from ERPNext `Portal User` links using `get_parents_for_user("Customer")`.
- The browser cannot supply or switch Customer identity.
- Quotation, Sales Order, Sales Invoice, Delivery Note and Project queries are constrained to those server-derived Customer records.
- Website-user permission bypass is used only after applying the same customer boundary used by ERPNext portal transaction controllers.

## Portal capabilities

- Quotations, orders, invoices, deliveries and projects with links to ERPNext native portal pages.
- Invoice billed, outstanding and overdue visibility.
- Overdue is derived from submitted Sales Invoice `due_date` plus positive `outstanding_amount`.
- Read-only submitted incoming Customer Payment Entry history. It is not presented as a wallet or available balance.
- Additive `Customer Portal` entry in Frappe Portal Settings, restricted to the Customer role.
- Client identity uses the configured Company where available; customer-facing copy does not expose product/vendor branding.

## Secure PDF downloads

Portal PDF download is intentionally separate from the Desk document-output endpoint.

- Supported document types: Quotation, Sales Order, Sales Invoice and Delivery Note.
- ERPNext `has_website_permission` is required for the logged-in Website User.
- The endpoint accepts only `doctype` and `name`; Customer identity and Print Format are never browser-selectable.
- Output uses the managed professional format only when it exists, is enabled, matches the DocType and is app-owned; otherwise it falls back to `Standard`.
- Letter Head remains enabled so the client Company controls customer-facing identity.
- The generated PDF is returned directly as a private response and no public file URL is created.

## EdgeSuite UI readiness

The website template uses shared EdgeSuite design tokens with safe fallbacks and carries `data-edge-suite-ready="true"`. It remains responsive for mobile and desktop customer access. Internal app/module/package identifiers remain stable but are not rendered as customer-facing branding.

## Accounting safety

The portal is read-only for accounting. It does not create or submit Payment Entries, allocate payments, mutate Sales Invoices, write GL Entry or Stock Ledger Entry, or calculate a parallel receivable balance. ERPNext accounting documents and outstanding values remain authoritative.
