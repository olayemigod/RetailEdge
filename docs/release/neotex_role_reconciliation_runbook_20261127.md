# Neotex Frappe Cloud — guarded RetailEdge role reconciliation

**Site:** `neotexapp.frappe.cloud`  
**Incident:** [RetailEdge #256](https://github.com/olayemigod/RetailEdge/issues/256)  
**Related release hold:** [RetailEdge #251](https://github.com/olayemigod/RetailEdge/issues/251)  
**Evidence date:** 2026-11-27  
**Status:** **DIAGNOSTICS COMPLETE; PRODUCTION CORRECTION AND MIGRATION NOT AUTHORIZED**

This is an operator/reviewer runbook, **not** an application patch, data migration, authorization to update the hosted site, or evidence that the site is healthy. No Neotex production records were changed while preparing it. Revalidate all facts against the staging clone, and obtain separate explicit authorization before **any** hosted write. The failed Update Site → Migrate Site is incomplete; model synchronization began, but the first RetailEdge post-model-sync patch aborted.

## 1. Exact migration failure and security invariant

`retailedge.patches.consolidate_duplicate_retailedge_roles` raises `frappe.ValidationError` at `_assert_permission_equivalence_before_merge`. The guard must not be skipped, marked applied, disabled, or changed to union privileges. It then independently checks:

1. Source and canonical `DocPerm` and `Custom DocPerm` scopes, **including** `if_owner`, `mask` and installed custom permission types.
2. Role security policy: `disabled`, `desk_access`, `two_factor_auth`, `restrict_to_domain`.
3. Source-only `Has Role` assignments and **all** other Link-to-Role authorization references.

The canonical cashier's `Account` permission is **Select-only** for native ERPNext invoice calculations, **not** Read or Export; do not copy legacy Account Read/Export into `RetailEdgeCashier`. Frappe/ERPNext role and field permissions remain authoritative. Preserving the current cashier workflow must not silently broaden the authority of canonical-only users.

Role mapping:

| Obsolete role | Canonical role |
| --- | --- |
| `RetailEdge Cashier` | `RetailEdgeCashier` |
| `RetailEdge Manager` | `RetailEdgeManager` |
| `RetailEdge Branch Manager` | `RetailEdgeBranchManager` |
| `RetailEdge Auditor` | `RetailEdgeAuditor` |

## 2. Verified hosted evidence — 15 known conflicting records or scopes

All observations below came from read-only Neotex Desk System Console queries supplied by the operator. **The listed counts cover the discovered conflicts, not a guarantee that no other patch or future upgrade failure exists.**

### A. Four legacy Cashier `Custom DocPerm` scopes

| DocType | Legacy `if_owner` | Legacy enabled standard flags | Canonical observed state | Decision and constraint |
| --- | ---: | --- | --- | --- |
| `Account` | 0 | Read, Export | No corresponding canonical custom row returned in the targeted query | Retire obsolete legacy grant if approved; canonical **Select-only** policy must be preserved. Confirm whether any operational code depends on legacy Account Read before change. |
| `Cost Center` | 0 | Read, Export | No corresponding canonical custom row returned | Do **not** automatically copy Read/Export. Test expense/category selectors and ordinary cashier posting; propose only minimum native permission if demonstrated necessary. |
| `RetailEdge Expense Category` | 0 | Read, Export | No corresponding canonical custom row returned | As above; verify authorized category selection/list usage and do not casually grant Export. |
| `RetailEdge Cashier Expense` | 1 | Read, Write, Create, Submit, Export, Share, Print, Email | Existing canonical row is `if_owner=0` with same flags **plus Report** | Owner-specific legacy scope and unrestricted canonical scope are intentionally treated as different. Review actual cashier expense ownership/branch restrictions and who gains access before any change; do not add an extra matching canonical owner-only row merely to suppress the guard. |

Other legacy `DocPerm` or custom-permission-type rows were not listed in the original failure; rerun the **full** preflight against the exact staging runtime before approval. Do not assume a missing canonical `Custom DocPerm` row means an absence of standard `DocPerm` rights.

### B. Ten legacy-only `Has Role` rows

- **Eight standard reports** — `RetailEdge Manager` and `RetailEdge Auditor` are each attached to the following four Reports, but their canonical counterparts were absent from Neotex's displayed Report roles:
  - `RetailEdge EdgePay Rollout Monitor`
  - `RetailEdge EdgePay Lifecycle Status`
  - `RetailEdge EdgePay Payment Evidence Summary`
  - `RetailEdge EdgePay Readiness Checklist`
- The **current RetailEdge source JSON** for these four standard Script Reports already declares `RetailEdgeManager` and `RetailEdgeAuditor` (along with System Manager, Accounts Manager and Accounts User). Compare the actual staged Report rows against the deployed app version. Restore intended canonical access and resolve obsolete legacy rows **without silently adding unrelated roles**.
- **One merchant-managed non-standard Query Report:** `Sales Person Sales by Invoice` (Sales Invoice). Existing role list includes `RetailEdge Cashier`, but not `RetailEdgeCashier`, plus `POSNext Cashier` and other merchant-selected roles. **Business policy decision required:** whether all canonical cashiers should retain this report. Adding canonical Cashier can broaden report access to future canonical-only users; removing legacy Cashier can narrow access. Neither is automatically approved. The observed duplicate Accounts Manager/Accounts User rows are outside this repair scope.
- **One Role Profile:** `cashier` has `POSNext Cashier`, `RetailEdge Cashier`, `Sales User`, `Stock User`. It does not yet have `RetailEdgeCashier`. **Zero** users had `role_profile_name='cashier'` at inspection time. Preserve the rest of the profile and replace obsolete role only after confirming its future access policy.

All nine directly legacy-assigned Cashier users already had canonical Cashier counterparts. The comparable Manager, Branch Manager and Auditor checks also found **zero missing direct User counterparts**. Therefore no direct User role assignment is currently proposed. Verify counts again before any write.

### C. One additional Link-to-Role child row

`RetailEdge Hidden Cost Price Role` row `9iehf07e7c` in `RetailEdge Settings.cost_price_hidden_roles` references `RetailEdge Cashier`.

At observation time, `RetailEdge Settings.hide_cost_price_for_selected_roles=0`; the configured list is `Stock User`, `RetailEdge Cashier`, `POSNext Cashier`, `Sales User`. Source `retailedge/cost_visibility.py` short-circuits the masking check when the toggle is disabled. **The current setting does not mask cost prices through this feature.** Do not claim otherwise or enable it as part of role migration. When the role is reconciled, preserve the intended list by replacing the old Cashier role with `RetailEdgeCashier` **without** disturbing the other three roles, so future activation uses the canonical role. Enabling masking later requires a separate security review and tests of all sensitive-cost paths.

### D. Other authority sources

- Both Cashier Roles: `disabled=0`, `desk_access=1`, `two_factor_auth=0`, `restrict_to_domain=None` — matching.
- Previously enumerated single-value Link-to-Role settings: **zero** fields contained a legacy RetailEdge role.
- No remaining non-`Has Role` Link-to-Role reference was found in the inspected ordinary DocField/Custom Field set other than the cost-price child row. Before execute, repeat preflight on the same staged code and metadata; the patch's `get_link_fields("Role")` may discover relationships beyond the basic inspector.

## 3. Safe deployment boundary and staging prerequisite

**Current approval: investigation and runbook preparation only.** Do **not** run any write code in Neotex System Console, delete/rename a role, directly alter SQL, edit Patch Log, skip the consolidation patch, retry the production upgrade, or overwrite the live site from a backup.

1. In the **Frappe Cloud Neotex site dashboard → Backups**, schedule an on-demand backup and verify that the database, public/private files and site config are present, identifiable, and restorable. Record backup ID/timestamp, site/app versions, bench group and previous good candidate. Frappe Cloud documentation: [Site Backups](https://docs.frappe.io/cloud/sites/backups).
2. Obtain approval to create an **isolated staging site** with the required same apps/compatible versions. Restore an independently verified Neotex backup using Frappe Cloud's **Restore Backup on another Site** option. The restore destination must be the staging site, **never the existing Neotex site**. Reference: [Restore & Migrate Site](https://docs.frappe.io/cloud/sites/migrate-an-existing-site). Restoration **overwrites the destination database**.
3. Keep staging separated from real commerce: disable outbound email/SMS/WhatsApp, payment-provider webhooks/callbacks, automatic invoice delivery, background automations and integrations that could affect customers or real transactions. Restrict staging user access. Confirm production remains serving its last known-good behavior (subject to the failed migration's incomplete state).
4. Snapshot/read-only export of the 15 affected entries and actual Role/Has Role/DocPerm/Custom DocPerm policy before rehearsing any write. Include created child-row names, field flags, ownership scopes, report role lists and cost visibility configuration; preserve private information securely.
5. Record business authorization specifically for (a) the nonstandard Sales Person report's canonical Cashier audience, (b) whether canonical Cashier Expense unrestricted `if_owner=0` behavior is intended, and (c) any genuine Cost Center/Expense Category operational reads required. If these are unresolved, the staging correction remains blocked.

## 4. Staging-only reconciliation procedure — after explicit approval

Use native Role Permission Manager / Report / Role Profile / RetailEdge Settings administration, or a narrowly scoped audited operator action. Do not use raw broad `DELETE` against `tabHas Role`, `tabCustom DocPerm`, or `tabRole`; do not silently copy legacy authority to canonical roles. Apply only after checking **exact original row identities and expected values**, and abort on any drift.

1. **Legacy Cashier custom grants:** retire only the four obsolete or conflicting *legacy* `Custom DocPerm` scopes **after** proving which cashier workflows rely on them. Do not grant Account Read/Export to the canonical role. Do not modify standard `DocPerm` indiscriminately. For Cost Center / Expense Category, test whether a specific least-privilege native Select or Read grant is necessary before discarding business functionality. For Cashier Expense, compare owner/branch-scoped API results before and after; do not infer that the canonical `if_owner=0` row is safe merely because it is present.
2. **Four standard EdgePay Reports:** compare the in-database role child rows to the four versioned JSON definitions and reconcile to canonical Manager/Auditor without broadening unrelated business report permissions. Remove only the stale legacy role links after explicit counterpart reconciliation; preserve Accounts/System Manager entries and report functionality.
3. **Merchant Query Report:** apply the separately approved decision for `Sales Person Sales by Invoice`, explicitly documenting authorized user/audience effect; retain all unrelated roles. Never assume the standard EdgePay report policy extends to this non-standard Report.
4. **Role Profile `cashier`:** replace `RetailEdge Cashier` with `RetailEdgeCashier`, retaining the three other roles, after confirming the profile still has zero active users and that the intended future permissions are accepted.
5. **Cost-price configuration:** replace the single obsolete child Link-to-Role value with `RetailEdgeCashier` only if the row and full list still match the verified evidence; leave `hide_cost_price_for_selected_roles=0`.
6. Rerun the **full** permission and role-link preflight before migration. The diagnostic in the patch is `get_role_permission_conflict_report()`, and migration itself checks role security policy and other Link-to-Role references. On the site where Bench is unavailable, use the approved read-only Desk System Console inspection or ask Frappe Cloud support to execute the existing diagnostic. Do not bypass a remaining conflict.

If the staged migration still raises `ValidationError`, stop, preserve logs and inspect **that** guard. Do not retry blindly or weaken it. The clone is the test site; successful migration there does **not** authorize Production migration.

## 5. Mandatory staging acceptance ledger

Capture observable PASS/FAIL, user persona, Company/Branch/shift, and before/after evidence for all applicable rows:

| Gate | Required check |
| --- | --- |
| Merge preflight | No unexplained role grant, Role policy, `Has Role`, or Link-to-Role differences; patch remains enabled and cannot be skipped. |
| Migration | Full app patches complete once on staging; safe rerun/idempotence; correct post-migrate metadata. |
| Cashier accounting safety | Cashier can **Select** authorized Account for native sales; cannot Read/Export unrelated Account/ledger information through RetailEdgeCashier alone; no privilege bypass. |
| POSNext cashier | POS launch, sales/invoice, saved sale, approved payment, shift close/EOD, manager override as applicable. |
| Cashier expense | Create/edit/submit authorized expense; deny cross-owner/cross-branch actions; compare before/after effective scope; no duplicate posting. |
| Master data | Cost Center and RetailEdge Expense Category selection/display as required, with no unauthorized Export or administrative access. |
| Reports | Canonical Manager/Auditor can open expected EdgePay reports, unauthorized roles cannot; explicit merchant decision for Sales Person report is respected. |
| Role Profile | New test user with the `cashier` profile receives the approved canonical authority; existing users' effective roles stay correct. |
| Cost visibility | Toggle remains **off** (no claimed masking protection); configured list correctly uses canonical Cashier; if later enabled, test masking in a **separate** change. |
| Operating scope | Company/Branch restrictions, direct APIs, native Advanced access and payment/GL/stock integrity preserved. |
| Recovery | Verified backup/restore procedure, exact app pins, rollback decision and communication plan approved. |

## 6. Production release hold

**STOP / NO-GO** until the staging clone is isolated, the 15 known records are reconciled against merchant-approved policy, all migration/permission/persona checks pass, and a separately authorized Production go/no-go references a recoverable backup and exact app release. Production role writes, site migration, deployments and release tags are **not authorized** by this runbook or by the operator's previous read-only console commands.

This is a site-specific historical-data reconciliation. The product safety check in `consolidate_duplicate_retailedge_roles.py` is not a defect to bypass.
