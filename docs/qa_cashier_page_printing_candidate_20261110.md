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
