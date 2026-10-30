# RetailEdge Cashier Access and Branding Audit — 2026-10-30

## Scope

This audit follows the `browser-cashier@example.com` acceptance pass on PR #239. It answers two questions:

1. Which RetailEdge destinations should a canonical `RetailEdgeCashier` see?
2. Why can a Company Profile logo uploaded by an administrator still render as a broken image for an operational role?

The change is presentation/access reconciliation. It must not manufacture transaction or accounting authority.

## Current platform baseline

The production candidate remains on the Frappe/ERPNext v16 line. At audit time the latest public releases are Frappe **v16.54.0** (2026-10-27) and ERPNext **v16.53.0** (2026-10-28). PR #239 continues to validate against its governed exact application candidate rather than silently upgrading dependencies inside this feature.

Relevant v16 behavior:

- Frappe v16 persistent sidebar guidance explicitly treats navigation as curated presentation: sidebar entries do not grant permission and inaccessible destinations should be omitted.
- Frappe public uploads are served from `/files/...`; private uploads are served from `/private/files/...` and require authorization when the file is fetched.
- Frappe's file manager supports saving a file with `is_private=0`, producing a public `/files/...` URL.
- POS products commonly separate transaction authority from device/printer configuration authority. A cashier/workstation user may need access to receipt-printer setup without receiving accounting or administration rights.

## Existing RetailEdge cashier authority

The canonical permission regression suite and migration establish the cashier as a daily sales/POS persona, not a general Sales or Accounts user.

### Native document permissions intentionally granted

`RetailEdgeCashier` receives:

- Company — read only.
- Branch, POS Profile, Warehouse, Mode of Payment, Customer, Item, UOM, Price List, Item Price — read/select.
- Sales Invoice — read, create, write, submit; no cancel/delete/amend.
- RetailEdge Cashier Expense — cashier-scoped operational create/read/write/submit through its existing role and server scope.

The role does **not** receive Payment Entry, Journal Entry, Purchase Invoice, Quotation, Sales Order or Delivery Note authority merely by being a RetailEdge cashier.

### RetailEdge/EdgeSuite Pages whose own boundaries already support the cashier

The audited presentation may therefore expose destinations that are independently permitted, including:

- My Work.
- Start POS.
- Make Sale / Sales Invoice operations where normal Sales Invoice permission permits them.
- Cashier Expenses.
- Expense Register, subject to its report capability and cashier row scope.
- Reports Centre, whose catalogue remains permission-filtered destination by destination.
- Operating Context.
- Company Profile as a read-only business identity view for a cashier; write/upload controls remain permission-driven.
- Devices & Printing (`edge-printing`), which is a shared EdgeSuite workstation/device surface and does not grant transaction authority.
- Document Output & Sharing, whose Page already includes the canonical cashier role and whose operations remain document-permission checked.
- Any other registry item that survives the existing native Frappe permission check and RetailEdge functional Page capability check.

### Explicitly not granted by this audit

Professional Selling is **not** added to `RetailEdgeCashier` by this change. Its Page currently excludes the cashier, and its principal Quote → Order → Delivery workflow relies on Quotation, Sales Order and Delivery Note permissions that the canonical cashier role does not have. Cashier Sales Invoice work remains available through Make Sale/POS/My Work.

Likewise this audit does not add banking, Payment Entry, Journal Entry, purchase, asset, warranty, management dashboard, audit-control, stock-management or financial-report authority.

## Root cause: sidebar regression

PR #239 added a second presentation projection after the normal permission-aware registry had already filtered navigation. That projection used a small hard-coded cashier allowlist and therefore removed legitimate surfaces such as Devices & Printing and Reports Centre even when their real permission boundaries allowed them.

The correction removes the persona allowlist. Final composition now preserves the already-authorized registry result and continues to apply functional Page checks for dashboards, reports, banking and native workspaces. The sidebar therefore follows effective permission truth instead of a duplicated cashier menu matrix.

## Company logo root cause and design

RetailEdge Company Profile is the presentation authority for the business logo used by the shared shell. The shell can correctly receive the logo URL while the browser still displays a broken image when that URL is under `/private/files/...`: private file access is checked independently when the image request is made.

A Company logo is tenant branding, not confidential business evidence. The selected design is therefore:

- keep Company Profile create/write/logo-change authority exactly as configured today;
- require logo selection to come from a File already attached to that Company Profile;
- if the selected file is private, create/reuse a public Frappe copy and persist its `/files/...` URL as the Company Profile logo;
- migrate existing private Company Profile logo references to public copies during `bench migrate`;
- preserve the original private File record instead of deleting unrelated evidence/history;
- do not grant cashiers generic File write permission or Company Profile write permission.

This makes the branding asset readable by every role while keeping branding mutation governed.

## Acceptance matrix

### Cashier sidebar

Expected visible when independently authorized:

- Home → My Work
- Point of Sale → Start POS / permitted POS operational links
- Sales → Make Sale / Sales Invoice / Document Output & Sharing as available
- Expenses → Cashier Expenses / Expense Register as available
- Reports → Reports Centre
- Business Setup → Operating Context / Company Profile / Devices & Printing
- other native read-only destinations only where the registry and Frappe permissions already allow them

Expected absent when not authorized:

- Professional Selling for the canonical cashier-only role
- Payment & Settlement Analysis
- banking/reconciliation controls
- accounting/financial statements
- purchase operations
- manager/auditor control surfaces
- asset/service workspaces without underlying authority

### Company logo

After migrate:

- the stored RetailEdge Company Profile logo URL is `/files/...` for an existing private logo;
- System Manager/authorized manager can still upload/change the logo;
- `RetailEdgeCashier` can render the Company logo without gaining profile/File mutation rights;
- ProcessEdge Retail product mark remains separate from the merchant Company logo.

## Validation required

1. Unit/contract tests for capability-driven navigation and private-to-public logo normalization.
2. Exact-head lint, integration, upgrade, EdgeSuite compatibility and browser-persona gates.
3. `retail.local` acceptance using `browser-cashier@example.com` after pull, migrate and asset build:
   - confirm the expanded permission-authorized sidebar;
   - confirm Professional Selling remains absent for cashier-only role;
   - open Reports Centre and verify only permitted report catalogue entries;
   - open Devices & Printing;
   - verify Company logo loads in the shell;
   - verify cashier still cannot open banking/accounting/management destinations directly.
