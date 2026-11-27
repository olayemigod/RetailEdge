# RetailEdge RC3 — Post-Merge Release Readiness (26 November 2026)

**Release hold: repository merges and automated CI are complete, but no deployment has been authorized.**

Authoritative evidence inventory: [`rc3_repo_merge_inventory_20261126.json`](rc3_repo_merge_inventory_20261126.json).
Tracking issue: [RetailEdge #251](https://github.com/olayemigod/RetailEdge/issues/251).

## 1. Immutable source and test evidence

| Component | Tested source | Merged destination |
| --- | --- | --- |
| RetailEdge 1.0.0 | `8e7f3a7c41ce565212fa7b14b4294341ee24db2d` | `version-16` at `b636632fd12bc01a9f1abee08bbf65922e8c245f` |
| ProcessEdge POSNext Extension 0.0.15 | `20fec40e45b76f7a086ad98954be4ee6e2870eea` | `main` at `374f517064755cfa56f20e8740a00721210d1f96` |

The merged Git trees were checked byte-identical to their pre-merge tested heads. RetailEdge's five exact-head release gates, the Extension's standalone and combined seven-app gates, and both post-merge push CI runs all passed (URLs in the JSON inventory). This does **not** establish that a specific live site runs these commits.

The verified *seven-app QA environment* used Frappe 16.52.0, ERPNext 16.51.1, EdgeSuite UI `d50920b005da8dcf1bd1e35c1c88be8afedecfbf`, POSNext v1.17.0 `44119bc9efa994bc096b037c3e9597068c9f4e8b`, Python 3.14, Node 24, and a CI-only Payments dependency. Do not silently switch to POSNext's tip or an untested EdgeSuite release.

**Important legacy manifest distinction:** `platform-baseline.json` is an older local six-app candidate and contains POSNext `0b8b6f3b...` and Extension `61a5fb9b...`. It is read by `scripts/verify-platform-baseline.py`, and the standalone CI intentionally uses its Frappe/ERPNext/EdgeSuite/Payments subset. The integrated seven-app CI independently pins the newer POSNext SHA and exact tested RetailEdge/Extension heads. The legacy JSON has **not** been changed by this documentation-only handoff, because replacing its values without checking every use of `--include-pos` could change or break its contract. The new JSON is a **human-reviewed evidence inventory, not a runtime resolver, installer or automatic deployment trigger**.

## 1A. CI baseline repair and evidence reconciliation — 27 November 2026

The original approved RC3 merge remains an immutable historical checkpoint at RetailEdge `b636632fd12bc01a9f1abee08bbf65922e8c245f`. Subsequent CI reruns identified failures on this **unchanged** baseline; they were documented in [Issue #253](https://github.com/olayemigod/RetailEdge/issues/253) and corrected through test-only [PR #254](https://github.com/olayemigod/RetailEdge/pull/254).

PR #254 passed **seven of seven exact-head CI jobs** at tested commit `3b6751329d59c85cf39710eb1912f39fc101a7d1`, including standalone Frappe v16, two EdgeSuite integration variants, frozen candidate upgrade, browser persona smoke, lint and dependency audit. It was merged on 27 November 2026. The verified current RetailEdge `version-16` head after this correction is `f46040f7d3822d306576a31a68bfe267b7a101f1`.

**Distinguish sources carefully:** the original RC3 seven-app release candidate and its source-equivalent merge still use the original RetailEdge source/merge SHAs in Section 1; the newer branch head contains **five test-fixture file changes only**, not business logic, permission bypasses, build rules or schema changes. The updated evidence inventory records both checkpoints rather than replacing the originally tested source identity. These CI results do **not** establish hosted site deployment or staging acceptance. The historical post-merge CI URL in the inventory was green on its original run; later reruns exhibited CI fixture failures, subsequently resolved by PR #254. Avoid calling it unconditionally green without this qualification.

**Release hold remains:** no staging or Production site updates, automatic deployment changes, schema migration, financial record repairs, new release tag or published GitHub Release have been authorized here.

## 2. Read-only deployment reconnaissance — no site operations

Record these facts **separately for local QA, staging, Neotex and every actual Production site**, without changing configuration:

- Exact Frappe Cloud team, bench group, bench/release identity, site, app list, current deployed **commit SHA**, installed DocTypes, Frappe/ERPNext/Python/Node versions, production custom domains and maintenance restrictions.
- Private versus public bench; deployed app release availability; any automatically selected release or `auto-deploy` bench marker; site automatic update schedule/status; pending Update Available/Deploy Candidate/failed builds and job history.
- Existing EdgeSuite runtime present before RetailEdge's asset-build guard runs; POSNext and Extension both present on the same bench/site where their functionality is required. Do **not** uninstall apps from an existing site just to change build order.
- Whether Frappe Cloud has already changed a site independently of these GitHub merges (never infer hosted state from Git branch status alone).

On a local bench that the operator is explicitly permitted to inspect, read-only diagnostics may include `bench version`, `bench --site <site> list-apps`, and `git -C apps/<app> rev-parse HEAD`. These diagnostics are **not** authority to pull, run `bench build`, migrate or restart.

Official Frappe Cloud guidance: [Updating a Bench](https://docs.frappe.io/cloud/benches/updating_a_bench), [App/Site Updates on Private Benches](https://docs.frappe.io/cloud/sites/how-to-update-an-app-site-on-a-private-bench), [Site Backups](https://docs.frappe.io/cloud/sites/backups) and [Disable Automatic Site Updates](https://docs.frappe.io/cloud/how-to-disable-auto-update-for-your-site). Frappe Cloud documents `auto-deploy`/`press-deploy` and automatic private-bench site updates; verify the **actual** bench and site configuration rather than assuming default behavior. Do not click Deploy, Update or Redeploy during reconnaissance.

## 3. Recovery preflight — required before any staging or Production change

1. Identify the site owner, maintainer/operator, bench provider and verified recovery contact.
2. Verify a complete and **recoverable** backup comprising database, public files, private files and relevant site configuration. Preserve encryption-key custody securely; do not commit keys, passwords or customer data to Git.
3. Record the original site app SHAs, ledger fingerprints/counts, known open POS shifts, outstanding receipts and customer-facing downtime constraints.
4. Obtain separate approval for a **staging-only** restore drill to an isolated site. Disable email/SMS/WhatsApp delivery, disable payment-provider callbacks, isolate queues/schedulers/Redis and ensure sensitive data is masked where appropriate. A backup existing is not the same as a successfully restored site.
5. Document a bounded rollback decision point. Before live transactions resume, restore the pre-upgrade site snapshot and prior app revisions, rebuild under the correct environment and compare GL/Stock Ledger controls. After new business transactions exist, **do not blindly restore an old database** and discard those transactions; use a separately approved incident recovery plan.

## 4. Controlled staging — requires its own explicit authorization

On a separately authorized staging site restored from representative data:

1. Pin Frappe/ERPNext/EdgeSuite/POSNext to the verified compatibility versions and source SHAs in the inventory; use the **merged** RetailEdge and Extension SHAs. Confirm Python 3.14 and Node 24 availability.
2. For a clean bench, follow dependency order: Frappe → ERPNext → EdgeSuite UI → POSNext → RetailEdge → ProcessEdge POSNext Extension. Payments in the seven-app test is a CI-only dependency, **not** an automatic merchant-site install requirement. For an existing bench, adjust releases without uninstalling an app from a live site.
3. Validate source commits and Python/Node dependencies, build the complete shared Desk asset graph with EdgeSuite available, then migrate the **staging** site. Run a second migration and recheck method override order, custom fields and role rules.
4. Compare pre/post submitted Sales Invoice, Payment Entry, GL Entry, Stock Ledger Entry and POS Closing Shift fingerprints and relevant counts. Do not use schema updates to repair historic accounting or mutate submitted transactions.
5. Verify light/dark responsive UI, permission-aware native Advanced, POSNext local held-sale behavior, and both browser and printer EOD paths.

### Staging acceptance matrix

| Case | Required evidence |
| --- | --- |
| Cashier positive workflow | Scoped login → Start POS → sale (including mixed Cash/Bank Draft), Cashier Expense, submitted Deposit Cash, expected/actual shift close and EOD print |
| Duplicate/misleading totals | No duplicate Cashier Expense action, cash receipts label matches collected tender, expenses and deposits deducted once, no second GL posting |
| Account least privilege | Cashier with Account **Select, not Read** can use permitted Cash account; unauthorised cashier cannot access arbitrary Account ledgers or Payment Entry operations |
| Shift/company scope | Wrong Company, Branch, cashier, POS Profile, cash source or target shift rejected by API, not just hidden by UI |
| Lifecycle safety | Draft/cancelled Deposit Cash excluded; attempts to submit a Deposit Cash draft after POS shift closure rejected |
| Concurrency | Expense versus Deposit Cash and two simultaneous spend attempts cannot overdraw or double-consume till funds |
| Role matrix | Cashier, Branch Manager, account-authorised user, read-only and no-access personas; print and Advanced controls only where permitted |
| History preservation | Prior submitted Ketu shift and accounting data unchanged; browser-local Held sale remains local, not claimed as server-persisted |

The user's earlier Ketu test passed for one closed shift: ₦10,000 expected/actual Cash, ₦2,000 Bank Draft, zero variance, end-of-day printed and incorrect 'No sales' label corrected. Later deposit-validation fixes have automated tests but still require separate manual staging acceptance on the merged code.

## 5. Final Production go/no-go — still blocked

Release requires: verified target Production inventory and auto-update settings; recovered staging restore; green staging acceptance matrix; baseline GL/stock/financial controls; approved deployment window; verified exact release selections and build ordering; communications and named rollback operator; and **separate explicit Production deployment authorization**.

**No Production pull, Frappe Cloud Deploy/Update/Redeploy, site migration, application install/uninstall, backups/restores on hosted sites, database corrections or automatic activation are approved by this document.**

Historic Neotex cash discrepancies are a separate accounting investigation, not a migration repair. Do not modify historic submitted accounting or shift records to make a release appear reconciled.
