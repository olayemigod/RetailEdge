# Role consolidation: non-destructive upgrade policy

## Reason
Frappe v16 `rename_doc("Role", ..., merge=True)` rewrites Role links. Some existing merchants and the upgrade-test predecessor site have different legacy and canonical `DocPerm`, `Custom DocPerm`, reviewer/approver or Page grants. Combining these can grant permissions never authorized for canonical-only users.

## Migration contract
The migration **preflights all role pairs before any mutation**. If either permission equivalence or authorization-link validation reports an issue, no Role, DocPerm, Custom DocPerm, Has Role, Role Profile, Page or reviewer/approver references are modified by this patch. The issue is recorded in standard Frappe Error Log as `RetailEdge role consolidation deferred`. The migration may then complete using the unchanged legacy/canonical data; **consolidation is not complete**.

Only if the entire preflight succeeds will the patch merge equivalent roles. There is no maximum/union of grants and no automatic change to merchant approval policy.

## Completion after explicit administration
1. Review Error Log details and the original Role Permission Manager, Role Profile, Page and reviewer/approver assignments. Obtain authorization to reconcile each conflicting permission; do not give canonical-only users legacy-only rights by default.
2. Backup the site and resolve the conflicting configuration in an isolated test environment, with evidence.
3. Rerun the idempotent routine only after the role permissions and authorization references are reconciled:

```bash
bench --site retail.local execute retailedge.patches.consolidate_duplicate_retailedge_roles.execute
```

4. Verify all affected personas and negative direct-API cases. Repeat on production only after separate acceptance.

Do not modify Frappe Patch Log to force replay. A completed upgrade does **not** prove all historical legacy roles have been retired.

## Release gates
The PR still needs five green exact-head hosted gates, independent full-scope review, user/branch/role/approval regression tests and recorded merchant acceptance on `retail.local`. Physical printing was user-reported PASS; receipt integrity and other merchant journeys remain distinct.
