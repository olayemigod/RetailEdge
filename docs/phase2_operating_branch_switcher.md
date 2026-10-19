# Operating Company and Branch Governance

## Business goal

RetailEdge gives each user an explicit **Operating Company** and **Working Branch** so daily work starts in the correct branch and document visibility follows the branch the user is currently operating. Users with genuine company-wide authority may deliberately choose **All Branches** for a Company-wide management view.

The context does not create a new accounting dimension and never rewrites historical Company, Branch, Warehouse or accounting truth.

## Permission model

RetailEdge composes with Frappe/ERPNext permissions rather than replacing them.

The effective visibility order is:

1. ERPNext/Frappe role permissions determine whether the user can read/create/write/submit the DocType at all.
2. Native User Permissions, `If Owner`, Workflow rules and document sharing continue to apply.
3. RetailEdge Branch Setup defines the valid Company→Branch universe.
4. Branch Assignment limits the Branches a restricted RetailEdge user may operate.
5. An explicitly selected Working Branch further narrows branch-attributed transaction reads to that one Company/Branch.
6. **All Branches** removes the Working Branch narrowing only for a user whose server-side scope is unrestricted, and it remains restricted to the selected Company.

RetailEdge permission hooks are subtractive only. They may deny a row that native permissions would otherwise allow; they never grant a document that ERPNext/Frappe denies.

### Same-Branch user isolation

A company may also choose that two users in the same Branch must not see each other's transactions. Use native ERPNext/Frappe permission configuration for this requirement:

- Role Permission Manager `If Owner` for roles whose users should see only documents they own;
- User Permissions for additional Link-based restrictions such as Branch, Customer or other governed masters;
- document sharing for a deliberate per-document exception.

RetailEdge custom lists must use permission-aware Frappe queries so these native restrictions remain effective. RetailEdge does not add a parallel `own transactions only` setting.

## Core contracts

1. Existing submitted or draft documents retain stored Company, Branch, Warehouse, POS Profile and accounting values.
2. Branch Setup is the Company→Branch binding authority. A Branch Assignment cannot make an unconfigured Company/Branch pair valid.
3. Optional Branch Setup defaults such as POS Profile, Warehouse, cost centre and payment accounts may be blank without hiding the configured Branch.
4. Explicit Working Branch selection is validated server-side and persisted as an explicit session context.
5. For RetailEdge-attributed ERPNext transactions, stored `retailedge_branch` is the authoritative branch field for Working Branch visibility.
6. RetailEdge branch-owned documents use their own stored `branch` field where applicable.
7. Selecting a Working Branch is a server-enforced read boundary, not merely a client ListView filter.
8. Direct document access must match the same Branch boundary as list/API queries; a hidden cross-branch row may not be reopened by URL or API.
9. All Branches is explicit Company-wide scope, not an empty-Branch bypass.
10. Branch-dependent creation, POS, stock and posting workflows still require a concrete valid Branch where the underlying transaction requires one.
11. An active POSNext shift or ERPNext POS Opening Entry can block a cross-branch or All Branches switch.
12. Current context guides new work only; it never mutates existing document attribution.

## Operating context service

The operating context service provides:

- `get_operating_context`
- `get_allowed_operating_contexts`
- `switch_operating_context`
- `switch_company_wide_context`
- `clear_operating_context`

The session override is cached for a bounded period and revalidated when read. Fallback/default context is retained for compatibility, but server transaction read narrowing begins only from an explicit session selection or from authoritative Branch Assignment restrictions. A fallback/default alone does not silently remove native ERPNext visibility from users who have not adopted RetailEdge Branch Assignment governance.

## Working Branch transaction visibility

Representative branch-attributed transactions include:

- Quotation
- Sales Order
- Delivery Note
- Sales Invoice / POS Invoice
- Purchase Order / Purchase Receipt / Purchase Invoice
- Supplier Quotation / Request for Quotation
- Payment Entry / Payment Request
- Material Request
- Stock Entry / Stock Reconciliation

For these documents:

- selected Ketu → Company + `retailedge_branch = Ketu`;
- selected Lagos Island → Company + `retailedge_branch = Lagos Island`;
- All Branches → selected Company only;
- restricted user without an explicit switch → active Branch Assignment Company/Branch pairs;
- unrestricted/native-only user without an explicit switch → no additional RetailEdge query condition.

The server condition is composed with native permission processing. `frappe.get_list` remains the normal query path for custom product lists so `If Owner`, User Permissions and sharing remain effective.

## Professional Selling correction

Professional Selling must resolve transaction branch identity by preferring `retailedge_branch` when that field exists, matching Professional Purchasing and the transaction-attribution layer. Generic/native Branch candidates are fallback only.

This prevents a Ketu Working Branch from returning a Lagos Island transaction merely because another Branch-like field is empty, stale or semantically different.

## Branch master visibility

RetailEdge operational roles require enough native permission to resolve a Branch master used by Branch Assignment and the selector. RetailEdge therefore grants its operational roles only:

- Branch Read
- Branch Select

It does not grant Branch Create, Write, Delete, Import or permission administration. User Permissions and Branch Assignment still determine which Branches may actually be operated.

## Client behavior

The shell and native ListView continue to reflect the active context for clarity:

- selected Branch adds/replaces the visible Company/Branch filters;
- All Branches removes the visible Branch filter while retaining Company;
- unrelated user filters such as Status or Date are preserved.

These UI filters are not the security boundary; the server permission layer is authoritative.

## Security and accounting safety

- No ERPNext/Frappe core modification.
- No permission bypass.
- No submitted-document rewrite.
- No fabricated Branch in All Branches mode.
- No cross-Company meaning for All Branches.
- No current Working Branch rewrite of historical documents.
- No custom own-document permission system when native `If Owner`/User Permission/sharing already provide it.
- Ambiguous or missing Branch attribution fails closed for Branch Assignment/session-restricted existing transactions.

## Automated acceptance

Required regression coverage includes:

- explicit Working Branch generates server Company+Branch conditions;
- All Branches retains Company and removes only Branch narrowing;
- Branch Assignment limits users without an explicit switch;
- users without Branch Assignment retain native ERPNext behavior;
- direct cross-Branch document access is denied under an explicit Working Branch;
- Professional Selling prefers stored `retailedge_branch`;
- custom selling lists use `frappe.get_list`, preserving native permission behavior;
- RetailEdge roles receive only minimum Branch Read/Select;
- restricted multi-Branch persona cannot activate All Branches;
- browser acceptance seeds one governed selling document in two Branches and proves Branch A cannot fetch/open Branch B while selected;
- unrestricted persona can deliberately broaden from one Branch to All Branches and see both within the same Company.

## Manual QA

Validate at minimum:

1. Global manager: Ketu shows only Ketu transactions; All Branches shows all authorized Branches in the Company; Lagos Island shows only Lagos Island.
2. Multi-Branch restricted user: only assigned Branches appear; All Branches does not appear; selected Branch limits lists and direct document access.
3. Single-Branch user: only that Branch is available and cross-Branch URL/API access fails.
4. Cashier persona: only permitted Branch/cashier surfaces remain visible.
5. Configure a QA role with native `If Owner` on a representative transaction DocType: two users in the same Branch see only their own documents.
6. Share one document explicitly and verify the configured native sharing exception without broadening the rest of the Branch.
7. Existing historical documents retain stored Branch/Company/accounting values after all context switches.
8. Active POS work blocks unsafe context changes.

## Closure

This work is complete only after the exact reconciled candidate passes Linters, full CI, Upgrade Validation, EdgeSuite compatibility, Browser Persona Smoke, and the required manual permission/Branch QA. A prior green SHA is invalid after any permission-scope change.
