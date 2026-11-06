# Make Sale Review, Recovery, and Cashier Output Audit — 2026-10-30

## Scope

This note records the bounded RetailEdge correction prompted by cashier acceptance on `retail.local`:

- a saved Sales Invoice draft could be submitted from Make Sale without enough visible transaction detail for an informed decision;
- a cashier had no durable product surface for finding an unfinished saved Make Sale draft after the browser/session path was broken;
- direct receipt printing correctly required Frappe `Print` permission, but the canonical RetailEdge cashier role had not been granted that permission for Sales Invoice;
- Document Output & Sharing already declared the cashier Page roles in source, but existing sites needed an explicit reconciliation patch so stale Page-role state could not block the route.

## Platform baseline and native truth

The current RetailEdge v16 audit baseline remains Frappe v16 / ERPNext v16. The preceding cashier-access audit recorded the then-current public releases as Frappe 16.54.0 and ERPNext 16.53.0; this bounded correction does not change the frozen application-set candidate.

Native behavior used by this change:

1. ERPNext Sales Invoice is a submittable document. `docstatus = 0` is Draft; `docstatus = 1` is Submitted. Submission is the point at which normal accounting and, when `Update Stock` is enabled, stock effects are posted.
2. Frappe permissions distinguish Read, Write, Submit, Print, Email, Report, and other capabilities. Read/Submit authority does not imply Print authority.
3. RetailEdge already delegates final Sales Invoice completion to ERPNext/Frappe validation, Workflow, document permissions, stock/accounting rules, and the existing `standard_sales_invoice_completion` boundary.
4. The existing Make Sale browser recovery is intentionally best-effort only. A saved ERPNext draft is the durable business record and therefore the correct recovery authority after a browser restart or lost session.

Primary references:

- ERPNext Sales Invoice documentation: https://docs.frappe.io/erpnext/sales-invoice
- Frappe DocStatus documentation: https://docs.frappe.io/framework/doctypes/docstatus
- ERPNext Role Based Permissions: https://docs.frappe.io/erpnext/permissions
- ERPNext/Frappe Print Settings: https://docs.frappe.io/erpnext/print-settings

## External workflow benchmark

Mature retail products commonly expose saved/open carts so an interrupted checkout can be resumed instead of forcing the operator to start over. Square for Retail, for example, lets staff save a cart and later reopen it to continue where they left off.

Reference: https://squareup.com/help/us/en/article/8238-build-your-customer-s-cart-in-the-square-retail-pos-app

RetailEdge deliberately does **not** copy a separate cart database for Make Sale. The ERPNext Sales Invoice draft already provides the durable transactional draft, so the RetailEdge equivalent is a permission-aware **Unfinished Sales** view over those native drafts.

## Chosen design

### 1. Informed submission review

`retailedge.sales_invoice_workbench.get_sales_invoice_submission_review` wraps the existing standard completion preview and enriches it with presentation detail only. The existing completion service remains the authority for:

- document Read/Submit permission;
- active Company/Branch context;
- standard-vs-return/POS boundaries;
- source document integrity;
- stock/Warehouse governance;
- Workflow readiness;
- blockers and timestamp-safe submission.

The enriched review includes the complete item list (not a first-N sample), Customer, Company, Branch, posting date, Selling Price List, stock-posting mode, discounts, taxes/charges, payments, totals, outstanding amount, and remarks.

Make Sale disables direct Submit unless the complete review contract is present. The operator sees the full review and receives a final confirmation naming the invoice and amount before the existing submit endpoint is called.

### 2. Durable unfinished-sale recovery

`get_resumable_sales_invoice_drafts` lists only:

- `Sales Invoice` drafts (`docstatus = 0`);
- owned by the signed-in user;
- non-POS, non-return, non-consolidated invoices supported by Make Sale;
- permitted by normal Frappe document permissions;
- valid for the current RetailEdge Company/Branch operating context;
- writable by the user.

The owner restriction is deliberate. A cashier cannot silently take over another cashier's unfinished sale merely because both work in the same Branch. A manager-level takeover policy, if ever desired, should be a separate explicit governance decision.

The Make Sale page exposes **Unfinished Sales** with Review and Resume Sale actions. Resume reloads the exact saved Sales Invoice and then uses the existing governed draft-edit path.

### 3. Cashier receipt/output access

Direct receipt generation already performs both Read and Print permission checks. That is retained.

The canonical RetailEdge cashier permission baseline now includes Sales Invoice `Print`. A new post-model-sync patch applies the permission to already-upgraded sites and reconciles both cashier role aliases onto the `document-output-sharing` Page. The patch does not grant Email, Export, Share, Accounts, or broader native Desk access.

This keeps the security model native and explicit rather than weakening the receipt service with a cashier-specific permission bypass.

## Deliberate non-goals

- No separate RetailEdge cart/order truth is introduced.
- No cross-cashier draft takeover is introduced.
- No Print permission bypass is added to receipt generation.
- No cashier Email permission is added; email remains independently permission-gated in Document Output & Sharing.
- No POSNext saved-cart implementation is changed.
- No ERPNext/Frappe core code is modified.

## Validation expectations

Automated and manual acceptance should prove:

1. a draft cannot expose the direct Submit action without the complete review contract;
2. every saved item is visible in the submission review;
3. displayed totals come from the saved ERPNext Sales Invoice, not client recomputation;
4. Refresh Review reloads the authoritative saved draft;
5. an interrupted cashier can find and Resume their own unfinished draft after a fresh browser session;
6. another cashier's draft is not listed by the recovery API;
7. Company/Branch context still constrains resumable drafts;
8. cashier Sales Invoice receipt printing succeeds when printer setup is valid because native Print permission is present;
9. Document Output & Sharing opens for both canonical cashier role aliases;
10. Email remains disabled unless independently permitted.
