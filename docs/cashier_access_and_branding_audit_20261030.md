# RetailEdge Cashier Access and Branding Audit — 2026-10-30

## Scope

This audit follows the `browser-cashier@example.com` acceptance pass on PR #239. It answers three questions:

1. Which RetailEdge destinations should a canonical `RetailEdgeCashier` see?
2. How should Professional Selling behave when a cashier has some, but not necessarily all, selling-document permissions?
3. Why can a Company Profile logo uploaded by an administrator still render as a broken image for an operational role?

The change is presentation/access reconciliation. It must not manufacture transaction or accounting authority.

## Current platform baseline

The production candidate remains on the Frappe/ERPNext v16 line. At audit time the latest public releases are Frappe **v16.54.0** (2026-10-27) and ERPNext **v16.53.0** (2026-10-28). PR #239 continues to validate against its governed exact application candidate rather than silently upgrading dependencies inside this feature.

Relevant v16 behavior:

- Frappe permissions are granular by document action: Read, Create, Write, Submit, Print, Email and other actions remain independent authorities.
- Draft documents (`docstatus = 0`) remain editable only where the current user has the required native permission/workflow authority.
- ERPNext selling remains document-driven: Quotation, Sales Order, Delivery Note, Sales Invoice and Payment Entry retain their own permissions and state rules.
- Frappe v16 persistent sidebar guidance treats navigation as curated presentation: sidebar entries do not grant permission and inaccessible destinations should be omitted.
- Frappe public uploads are served from `/files/...`; private uploads are served from `/private/files/...` and require authorization when the file is fetched.
- POS products commonly separate transaction authority from device/printer configuration authority. A cashier/workstation user may need access to receipt-printer setup without receiving accounting or administration rights.

## Existing RetailEdge cashier authority

The canonical permission regression suite and migration establish the cashier as a daily sales/POS persona, not a general Sales or Accounts user.

### Native document permissions intentionally granted

`RetailEdgeCashier` receives:

- Company — read only.
- Branch, POS Profile, Warehouse, Mode of Payment, Customer, Item, UOM, Price List, Item Price — read/select.
- Sales Invoice — read, create, write, submit and print; no cancel/delete/amend/email.
- RetailEdge Cashier Expense — cashier-scoped operational create/read/write/submit through its existing role and server scope.

The canonical role does **not** receive Payment Entry, Journal Entry, Purchase Invoice, Quotation, Sales Order or Delivery Note authority merely by being a RetailEdge cashier. A particular user may nevertheless receive additional native selling permissions through another assigned role or a deliberate customer permission design.

## Professional Selling: permission-aware workspace, not persona gate

Professional Selling is an EdgeSuite workspace over ERPNext selling documents. Its Page must therefore not block a user merely because the user is a cashier when that user already has legitimate selling-document authority.

The corrected contract is:

- both canonical and legacy RetailEdge cashier role names may open the `professional-selling` Page;
- opening the Page grants **no** Quotation, Sales Order, Delivery Note, Sales Invoice or Payment Entry permission;
- the workspace displays a document stage only when that document is available and the current user can read or create it;
- create controls remain tied to the document's native Create permission;
- record lists remain tied to native Read permission and current Company/Branch scope;
- draft edit/completion and submission continue through the existing permission/workflow-aware completion endpoints;
- conversion actions appear only when the downstream document can be created and the source record is in a valid state; every conversion endpoint revalidates permissions and Company/Branch context;
- customer payment actions remain independently gated by Payment Entry authority and the guided-payment server boundary;
- Print & Share continues through the document-output permission boundary;
- Native Desk remains an Advanced escape only where the user is independently allowed to use it.

Therefore a role-exact `RetailEdgeCashier` currently sees Sales Invoice capability inside Professional Selling because Sales Invoice is the selling document that role owns. If that same user is deliberately granted Quotation, Sales Order or Delivery Note authority, those corresponding stages and allowed actions appear automatically without another RetailEdge persona change.

This is the intended distinction between **workspace access** and **business authority**.

## RetailEdge/EdgeSuite Pages whose own boundaries support the cashier

The audited presentation may expose destinations that are independently permitted, including:

- My Work.
- Start POS.
- Make Sale / Sales Invoice operations where normal Sales Invoice permission permits them.
- Professional Selling as the permission-aware selling workspace described above.
- Cashier Expenses.
- Expense Register, subject to its report capability and cashier row scope.
- Reports Centre, whose catalogue remains permission-filtered destination by destination.
- Operating Context.
- Company Profile as a read-only business identity view for a cashier; write/upload controls remain permission-driven.
- Devices & Printing (`edge-printing`), which is a shared EdgeSuite workstation/device surface and does not grant transaction authority.
- Document Output & Sharing, whose operations remain document-permission and Company/Branch checked.
- Any other registry item that survives the existing native Frappe permission check and RetailEdge functional Page capability check.

### Explicitly not granted by this audit

Professional Selling Page access does not itself add Quotation, Sales Order, Delivery Note or Payment Entry authority. It also does not add banking, Journal Entry, purchase, asset, warranty, management dashboard, audit-control, stock-management or financial-report authority.

A cashier who lacks Payment Entry Create permission must not receive a Make Payment action merely because Professional Selling is visible. If ProcessEdge later chooses to make customer-payment collection an inherent `RetailEdgeCashier` capability, that requires a separately governed, constrained customer-receipt design rather than silently giving the role broad accounting authority.

## Root cause: sidebar regression

PR #239 added a second presentation projection after the normal permission-aware registry had already filtered navigation. That projection used a small hard-coded cashier allowlist and therefore removed legitimate surfaces even when their real permission boundaries allowed them.

The correction removes the persona allowlist. Final composition now preserves the already-authorized registry result and continues to apply functional Page checks for dashboards, reports, banking and native workspaces. Professional Selling follows the same rule: its Page can be shown to the cashier, while the workspace itself derives usable documents/actions from effective native permission truth.

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
- Sales → Make Sale and Professional Selling
- Sales → Document Output & Sharing as available
- Expenses → Cashier Expenses / Expense Register as available
- Reports → Reports Centre
- Business Setup → Operating Context / Company Profile / Devices & Printing
- other native read-only destinations only where the registry and Frappe permissions already allow them

Inside Professional Selling, the exact stages/actions are permission-derived. The role-exact browser cashier is expected to see Sales Invoice but not Quotation, Sales Order or Delivery Note because those extra native document permissions are intentionally absent from the test persona.

Expected absent when not authorized:

- Payment actions without Payment Entry authority
- Quotation/Sales Order/Delivery Note stages where those native permissions are absent
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

1. Unit/integration contracts for capability-driven navigation, Professional Selling Page access and private-to-public logo normalization.
2. Browser acceptance proving a role-exact cashier can open Professional Selling while unavailable document stages/payment actions remain absent.
3. Exact-head lint, integration, upgrade, EdgeSuite compatibility and browser-persona gates.
4. `retail.local` acceptance using `browser-cashier@example.com` after pull, migrate and asset build:
   - confirm the permission-authorized sidebar;
   - open Professional Selling and confirm Sales Invoice is usable;
   - confirm Quotation/Sales Order/Delivery Note appear only when that user has the corresponding native authority;
   - confirm draft edit/completion, conversion and payment actions follow effective permissions/document state;
   - open Reports Centre and verify only permitted report catalogue entries;
   - open Devices & Printing and Document Output & Sharing;
   - verify Company logo loads in the shell;
   - verify cashier still cannot open banking/accounting/management destinations directly.
