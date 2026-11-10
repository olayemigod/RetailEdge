# Cashier My Work: standard Page checkout mismatch — 10 November 2026

## Incident
A user assigned the RetailEdge cashier role opened `/app/cashier-my-work` on
`retail.local`. Frappe 16.52 `frappe.desk.desk_page.getpage` raised:

```
FileNotFoundError: [Errno 2] No such file or directory:
'apps/retailedge/retailedge/retailedge/page/cashier_my_work'
```

This is **not a cashier permission failure**: Frappe had already fetched an
authorized `Page` row and attempted `Page.load_assets()`. It failed before
loading the cashier Vue page.

## Verified repository explanation

- The deployed site's database still has a standard `Page` record for
  `cashier-my-work`.
- The original `version-16` head `c6384fcb`, and printing PR #248
  `04c7819f` branched from it, **do not contain** the corresponding
  standard Frappe page folder, component, or self-service endpoint.
- User-onboarding PR #239 `1c7dde92` **does contain** the Page JSON, Page
  JavaScript/Python, frontend bundle, Vue page and cashier API.
- The immediate checkout of PR #248 to test Document Output printing therefore
  excluded the unmerged PR #239 feature, while the existing site's database
  Page record remained routable. App semantic versions alone do not identify
  the underlying Git candidate.
- This QA candidate starts from **exact PR #239 head**, then includes the
  bounded, non-overlapping PR #248 printing corrections so both cashier work
  and direct receipt printing remain present. Original PRs remain untouched.

## Reconciliation and safety contract

- No live Page records are deleted and no Page permissions are widened to hide
  the mismatch. The correct fix is to deploy a complete and compatible code
  candidate, not to recreate a fake Page or bypass Frappe permission checks.
- `Page` metadata (module/name/roles) is backed by actual
  `retailedge/retailedge/page/cashier_my_work` assets in the installed app.
- Frappe 16.52's `frappe.desk.desk_page.get` calls
  `Page.load_assets()` through the same path as `getpage`. Added a
  regression test exercising that operation on an installed site.
- The exact RetailEdge cashier role stays on the Page, and existing
  company/branch ownership checks stay on `cashier_self_service` API.
- Combined candidate preserves existing EdgeSuite runtime pin from PR #239;
  real MPT-II cross-tab QA must additionally use the separately tested shared
  EdgeSuite UI PR #53 candidate. Do not change the distribution dependency
  silently.
- Run targeted cashier Page/regression and receipt tab tests plus
  Frappe v16.52 install/migrate/asset CI. Check cashier persona with
  `frappe.desk.desk_page.getpage(name="cashier-my-work")`, its home/launcher,
  POS, receipts, theme, and no cross-Branch document exposure.

## Local QA deployment

Before replacing any app checkout, preserve local uncommitted work. The
integrated branch is `qa/cashier-my-work-print-reconciliation-20261110`.
Pin the exact verified SHA from GitHub, rebuild RetailEdge assets, migrate
against a backed-up site if required, and clear cache. Verify physically
printing and cashier navigation in the same running app checkout. Do not
switch to PR #248 alone or PR #239 alone after this test; either switch
would drop one feature again.

The feature is **not accepted** merely because the branch contains its Page
folder. Successful cashier route retrieval, permission checks, builds, and
runtime acceptance are required.

## Follow-up browser-console evidence: Page row missing after checkout

The next cashier browser-console capture reported
`frappe.exceptions.DoesNotExistError: Page cashier-my-work not found`
while `frappe.desk.desk_page.getpage` returned HTTP 403. This is **different**
from the previous `FileNotFoundError`: the new candidate contains the standard
Page folder, but the current site's database may not yet contain the
corresponding `Page` record, or the runtime may be using a different checkout
than expected. The raised `PermissionError` follows the missing Page
resolution; it is not evidence that assigning extra cashier roles fixes it.

**Repair on the backed-up `retail.local` site, without deleting records or
granting permissions:**

1. Confirm `git -C apps/retailedge rev-parse HEAD` is the exact integrated
   PR #249 candidate, with a clean tree and
   `retailedge/retailedge/page/cashier_my_work/cashier_my_work.json` present.
2. Check `bench --site retail.local execute frappe.db.exists --args
   '["Page", "cashier-my-work"]'`. An absent record means frontend
   rebuild/cache clearing alone cannot register the standard Page.
3. Run `bench --site retail.local backup`, then
   `bench --site retail.local migrate`, to reconcile Frappe's standard
   Page JSON and DocType records with the installed application. If the
   standard Page is still missing, inspect the migrate log before considering
   a targeted `bench --site retail.local reload-doc retailedge page cashier_my_work`.
4. Repeat the Page-exists check, restart bench processes if stale, clear cache,
   and test as the cashier. An existing Page that denies its authorized
   cashier must be investigated as a **separate** permission issue.
5. Avoid switching the site back to only PR #248 (which has no My Work
   source) without restoring a matched Page/code candidate.

Other independent Console findings: Chrome's `https://retail.local:9000`
Socket.IO TLS protocol errors indicate a misrouted realtime connection in
the local HTTPS/Caddy setup; they do not cause `Page ... not found`.
`contentscript.js` event-listener warnings originate in injected browser
scripts and cannot be assigned to RetailEdge from this capture. The
`aria-hidden` focused-dialog warning is a separate accessibility follow-up.

**Browser CI reconciliation:** The legacy cashier smoke expected the
Business Hub heading at the cashier landing route, but the accepted cashier
home is now My Work. A focused test now opens `cashier-my-work` directly
while preserving negative Banking Readiness checks; do not weaken restricted
page denial tests to make smoke green. No production merge/deployment.

## Cashier and Branch Manager acceptance findings — 10 November 2026

Operator confirmation: **saved sale resume/edit/update passes** on the local bench.
Cashier **Receive Payment fails with "No permission for Payment Entry"**.
Branch Manager opens Professional Selling, but the Quotation, Sales Order,
Delivery Note and Sales Invoice cards/lists are not visible.

### Cashier native Payment Entry failure: reproduced in CI

An exact-head browser acceptance test against a real ERPNext 16.51.1
Payment Entry reproduced the user's error. The traceback enters
`cashier_customer_receipt._post_native_payment -> payment.insert ->
Payment Entry.validate -> set_missing_values -> get_account_details`.
ERPNext's `get_account_details` requires **generic Payment Entry Read**
permission even though RetailEdge's constrained cashier receipt intentionally
does not grant any general Payment Entry rights. The earlier
`ignore_permissions=True` on insertion does not waive this separate
whitelisted account-details helper check.

The bounded correction verifies the exact invoice Debtors/Receivable account,
Company, account type, currency, active/non-group state and the already
resolved receiving Cash/Bank Mode of Payment. It then supplies the native
`paid_from_account_currency`, `paid_from_account_type`,
`paid_to_account_currency`, and `paid_to_account_type` before calling
ERPNext Payment Entry insertion. Consequently the native
`set_missing_values` does not invoke the generic account-details helper.
ERPNext still controls the document's validation, submission, reference
allocation, GL and payment ledger. Cross-Branch identity, invoice read,
posting-mode, workflow and invoice concurrency checks stay server-enforced.
**Do not grant Payment Entry DocPerm to cashiers** as a workaround.

Acceptance requires a green ephemeral-CI real POST test (partial receipt,
posted Payment Entry and outstanding reduction), followed by one local cashier
UI review/confirmation on a deliberately safe test invoice. A previous CI
`saved sale` test also timed out with an Update Draft button disabled even
though the local operator confirmed the workflow passes; diagnose test
setup/preview readiness separately rather than declaring the feature broken
or disabling governance.

### Branch Manager: DocType rights are independent of the product role

The source and v16.51.1 native DocPerm matrix confirm that
`RetailEdgeBranchManager` grants branch-operating context but **does not
implicitly grant** Quotation, Sales Order, Delivery Note or Sales Invoice
rights. Professional Selling intentionally renders only capabilities for
which Frappe reports `can_read` or `can_create`. An operator with just
that product role therefore gets an empty document area. This is a native
role-configuration gap and a deficient empty state, **not grounds to bypass
native permissions**.

To enable authorized selling for a Branch Manager, an administrator should
choose the appropriate *native* Roles/Role Permission Manager configuration,
and retain Company/Branch scope. Frappe/ERPNext 16.51.1 `Sales User`
covers Quotation, Sales Order and Delivery Note; **Sales Invoice instead
requires explicitly governed invoice rights**. A broad `Accounts User`
role also permits Journal Entry creation, so do **not** automatically assign
it merely to make the invoice card appear. For read-only oversight, configure
a scoped native read-only Role for the exact four document types rather than
granting transactional submit privileges.

The page now visibly explains lack of selling-document access without
granting roles. Verify with the existing restricted Branch Manager persona
and a separately authorized manager persona; negative cross-branch/Advanced
access checks remain essential. If the user already has native rights but
the cards are still empty, inspect the exact `get_professional_selling_context`
and `get_professional_sales_invoice_capability` responses and refresh the
Frappe role cache instead of inventing documents or replacing filters.
