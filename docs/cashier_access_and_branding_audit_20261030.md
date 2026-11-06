# RetailEdge Cashier Access and Branding Audit — 2026-10-30

## Scope

This audit follows the `browser-cashier@example.com` acceptance pass on PR #239. It answers four questions:

1. Which RetailEdge destinations should a canonical `RetailEdgeCashier` see?
2. Which ERPNext selling documents should the canonical cashier operate through Professional Selling?
3. Why could different RetailEdge routes show different sidebar contents for the same cashier?
4. Why can a Company Profile logo uploaded by an administrator still render as a broken image for an operational role?

The governing rule is permission-first: navigation exposes authorized work but does not itself grant authority. ERPNext documents, DocPerm, Workflow, document state and RetailEdge Company/Branch scope remain authoritative.

## Current platform baseline

The production candidate remains on the Frappe/ERPNext v16 line. At audit time the latest public releases are Frappe **v16.54.0** (2026-10-27) and ERPNext **v16.53.0** (2026-10-28). PR #239 continues to validate against its governed exact application candidate rather than silently upgrading dependencies inside this feature.

Relevant v16 behavior:

- Frappe permissions are granular by document action: Read, Create, Write, Submit, Print, Email and other actions remain independent authorities.
- Draft documents (`docstatus = 0`) remain editable only where the current user has the required native permission/workflow authority.
- ERPNext selling remains document-driven: Quotation, Sales Order, Delivery Note, Sales Invoice and Payment Entry retain their own permissions and state rules.
- Frappe navigation is presentation; sidebar entries do not grant permission and inaccessible destinations should be omitted.
- Frappe public uploads are served from `/files/...`; private uploads are served from `/private/files/...` and require authorization when the file is fetched.

## Canonical RetailEdge cashier authority

The cashier is a daily POS and customer-selling persona, not a general Accounts or back-office user.

### Native master/reference access

`RetailEdgeCashier` receives the read/select access required for selling and POS context, including:

- Company — read only.
- Branch, POS Profile, Warehouse, Mode of Payment, Customer, Item, UOM, Price List and Item Price — read/select.

### Governed selling-chain permissions

The canonical cashier receives the same bounded operational permission set on:

- Quotation
- Sales Order
- Delivery Note
- Sales Invoice

For each of those documents the role receives:

- Read
- Create
- Write
- Submit
- Print

The role does **not** receive Cancel, Delete, Amend or Email by default. Native ERPNext validation, Workflow, stock/accounting rules, document state and RetailEdge Company/Branch scope remain authoritative.

This makes Professional Selling a complete everyday cashier selling workspace: a cashier can quote, take an order, fulfil/deliver where appropriate, invoice, edit permitted drafts, submit permitted documents and use downstream conversions when ERPNext allows them.

### Accounting authority remains separate

The canonical cashier still does **not** receive generic Payment Entry, Journal Entry or Purchase Invoice authority merely by being a cashier.

Customer-payment collection therefore remains a distinct capability decision. Professional Selling may expose payment actions only where the current user has the required payment authority. If ProcessEdge makes customer-payment collection inherent to the cashier role, it should use a constrained customer-receipt boundary scoped to permitted customer documents, Company/Branch and approved payment modes rather than silently granting broad accounting access.

This audit intentionally does not solve that separate payment-capability design; it preserves the existing Payment Entry boundary while fixing selling-document and navigation access.

## Professional Selling: permission-aware workspace

Professional Selling is the EdgeSuite everyday workspace over ERPNext selling truth.

The corrected contract is:

- both canonical and legacy RetailEdge cashier role names may open the `professional-selling` Page;
- the cashier operational permission baseline supplies the governed Quotation → Sales Order → Delivery Note → Sales Invoice authority described above;
- opening the Page itself still grants no document authority;
- the workspace displays a document stage only when that document is available and the current user can read or create it;
- create controls remain tied to native Create permission;
- record lists remain tied to native Read permission and current Company/Branch scope;
- draft edit/completion and submission continue through the existing permission/workflow-aware completion endpoints;
- conversion actions appear only when the downstream document can be created and the source record is in a valid state; target endpoints revalidate authority and Company/Branch context;
- payment actions remain independently gated by the governed payment boundary;
- Print & Share remains independently document-permission checked;
- Native Desk remains an Advanced escape only where independently authorized.

For a role-exact canonical cashier, Professional Selling is expected to expose all four selling stages: **Quotation, Sales Order, Delivery Note and Sales Invoice**.

## One sidebar contract across RetailEdge routes

My Work, Professional Selling, Reports Centre and the other EdgeSuite pages are intended to render the **same final permission-aware Business Hub navigation**, not page-specific cashier menus.

The inconsistency found during browser acceptance had two causes:

1. Earlier PR work had introduced a second cashier presentation projection that could subtract valid destinations after the normal permission-aware registry had already filtered them. That allowlist has been removed.
2. Frappe Desk keeps Page/Vue instances mounted across route changes. My Work could therefore keep an older navigation snapshot while a newly opened Professional Selling page resolved a newer one. The shared Business Hub context is also cached briefly in the browser. This made two routes appear to have different sidebars even though they were intended to use the same server contract.

The correction is:

- final navigation remains owned by `navigation_consolidation.get_retailedge_business_hub_context`;
- My Work clears the shared navigation cache and reloads its mounted component when the route is shown again;
- Professional Selling clears the same cache before its page-show refresh;
- Reports Centre obtains its sidebar from the same final navigation contract rather than its older report-context snapshot;
- browser acceptance traverses My Work → Professional Selling → My Work and requires Professional Selling to remain present throughout.

A route change must therefore not add or remove sidebar capabilities unless the user's effective permissions, readiness or operating context actually changed.

## RetailEdge/EdgeSuite Pages whose own boundaries support the cashier

Expected destinations include, where independently permitted:

- Home → My Work
- Point of Sale → Start POS and permitted POS operational links
- Sales → Make Sale
- Sales → Professional Selling
- Sales → Document Output & Sharing
- Expenses → Cashier Expenses / Expense Register as applicable
- Reports → Reports Centre
- Business Setup → Operating Context / Company Profile / Devices & Printing
- other registry destinations that survive native Frappe permission and RetailEdge functional capability checks

Professional Selling provides the normal Quotation, Sales Order, Delivery Note and Sales Invoice journey rather than advertising separate native DocType routes as the everyday experience.

### Explicitly not granted by this audit

The selling permission correction does not add:

- generic Payment Entry or Journal Entry authority;
- banking/reconciliation controls;
- purchasing authority;
- management/audit dashboards without their own permission;
- asset/service/warranty workspaces without underlying authority;
- financial statements merely because Reports Centre is accessible.

## Reports Centre navigation consistency

Reports Centre is a catalogue of permitted report destinations, not a second navigation authority. Its EdgeSuite shell must use the same final sidebar contract as My Work and Professional Selling.

Opening Reports Centre must not cause hidden groups such as Asset Management or Service & Warranty to reappear for a cashier when the final navigation contract has filtered them out.

## Company logo root cause and design

RetailEdge Company Profile is the presentation authority for the business logo used by the shared shell. The shell can correctly receive the logo URL while the browser still displays a broken image when that URL is under `/private/files/...`: private file access is checked independently when the image request is made.

A Company logo is tenant branding, not confidential business evidence. The selected design is therefore:

- keep Company Profile create/write/logo-change authority exactly as configured;
- require logo selection to come from a File already attached to that Company Profile;
- if the selected file is private, create/reuse a public Frappe copy and persist its `/files/...` URL as the Company Profile logo;
- migrate existing private Company Profile logo references to public copies during `bench migrate`;
- preserve the original private File record instead of deleting unrelated evidence/history;
- do not grant cashiers generic File write permission or Company Profile write permission.

This makes the branding asset readable by every role while keeping branding mutation governed.

## Acceptance matrix

### Cashier selling

Expected:

- Professional Selling is visible under Sales from My Work and other RetailEdge routes.
- Professional Selling exposes Quotation, Sales Order, Delivery Note and Sales Invoice.
- Draft editing, submission and conversions appear only when native state/workflow permits them.
- Sales documents remain Company/Branch scoped.
- Print is available on the governed selling documents.
- Cancel/Delete/Amend/Email remain unavailable unless separately granted.
- generic Payment Entry remains unavailable until a separate payment-capability decision is implemented.

### Sidebar consistency

Expected across My Work, Professional Selling and Reports Centre:

- the same permission-authorized navigation families are present;
- route changes do not restore stale or hidden menu groups;
- Professional Selling remains under Sales after navigating away and back;
- Asset Management and Service & Warranty remain absent for a role-exact cashier when their underlying authority is absent.

### Company logo

After migrate:

- the stored RetailEdge Company Profile logo URL is `/files/...` for an existing private logo;
- System Manager/authorized manager can still upload/change the logo;
- `RetailEdgeCashier` can render the Company logo without gaining profile/File mutation rights;
- ProcessEdge Retail product mark remains separate from the merchant Company logo.

## Validation required

1. Integration tests proving the role-exact cashier has Read/Create/Write/Submit/Print on Quotation, Sales Order, Delivery Note and Sales Invoice while broad accounting authority remains absent.
2. Browser acceptance proving all four Professional Selling stages are visible to the role-exact cashier.
3. Browser acceptance proving My Work → Professional Selling → My Work keeps the same final sidebar and does not restore unauthorized groups.
4. Exact-head lint, integration, upgrade, EdgeSuite compatibility and browser-persona gates.
5. `retail.local` acceptance after pull, migrate and asset build:
   - confirm Professional Selling under Sales on My Work;
   - open Professional Selling and confirm all four selling stages;
   - exercise permitted draft edit/completion and conversion paths;
   - return to My Work and confirm Professional Selling remains in the sidebar;
   - open Reports Centre and confirm unauthorized Asset/Service groups do not reappear;
   - verify Devices & Printing, Document Output & Sharing and Company logo remain available as governed;
   - verify banking/accounting/management destinations remain absent where unauthorized.
