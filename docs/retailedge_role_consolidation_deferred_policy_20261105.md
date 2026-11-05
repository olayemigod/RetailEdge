# Role consolidation — strict upgrade stop and administrator reconciliation

## Historical collision
Existing RetailEdge installations and the hosted upgrade predecessor contain both spaced legacy roles (for example `RetailEdge Cashier`) and canonical roles (`RetailEdgeCashier`) with different DocPerm, Custom DocPerm, Frappe v16 Permission Type, User/Role Profile/Page, reviewer/approver or Role-level security settings (including mandatory 2FA).

Frappe v16 `rename_doc("Role", ..., merge=True)` rewrites Role Link references and keeps the destination Role's security policy. Automatically unioning grants or remapping an approver role could expand authorization for canonical-only users.

## Mandatory preflight and failure
The consolidation patch checks **all role pairs before any rename or permission-row mutation**:
- every installed native and custom permission column, including `if_owner`, `mask` and custom Permission Types;
- Role `two_factor_auth`, `disabled`, `desk_access` and `restrict_to_domain`;
- Has Role, Role Profile, Page and other authorization-bearing Role links.

If any source/destination role differs, it raises `frappe.ValidationError` and **stops the upgrade**. Neither role is merged; no legacy permissions are silently added to the canonical role. Do not suppress or catch this exception to let the remaining patches run: model synchronization and subsequent Page governance patches may alter effective rights even if Role records remain in place.

If all checks pass, the patch merges only equivalent roles and is repeat-safe.

## Administrator reconciliation on an isolated site
1. Back up the existing database. Record all conflicting permission rows and reviewer/approver policies before altering permissions.
2. Review the permitted effective rights of legacy-only, canonical-only and dual-role users, including User/Role Profile, Page, Branch, and payment/approval direct API access. Define an explicit least-privilege mapping; do not copy all legacy grants into canonical roles.
3. Reconcile the original source data with an authorized administrator on a test site. Retest the upgrade and all relevant persona/Branch tests before any production migration.
4. Confirm each failed gate has passed on the **same exact PR head** and complete the merchant acceptance ledger. Do not edit Frappe Patch Log or use a manual data rewrite simply to make CI pass.

The previous proposal to continue migration while logging deferred roles was rejected after review demonstrated that post-model-sync and subsequent Page patches could still change effective authorization. **A blocked upgrade is the intended safe outcome until the historical conflicts are resolved.**

## Release boundary
PR #238 remains Draft and may not merge with a failed Upgrade Validation gate or unresolved P1 review. Physical printing on `retail.local` was user-reported PASS, but other merchant acceptance and receipt-integrity cases remain separate. PR #239 requires integration against #238's eventual accepted head.
