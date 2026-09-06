# Pre-reporting RetailEdge role normalization

## Goal

Remove ambiguity between compact and spaced RetailEdge role names before reporting/persona QA without breaking existing installations, DocType permissions, or EdgeSuite access behavior.

## Canonical internal role IDs

RetailEdge keeps its long-standing compact role IDs as the canonical internal contract:

- `RetailEdgeCashier`
- `RetailEdgeManager`
- `RetailEdgeBranchManager`
- `RetailEdgeAuditor`

This is an internal compatibility decision. It does not prevent product UI from using human-readable labels such as Cashier, Manager, Branch Manager, or Auditor.

## Compatibility aliases

Only spaced names already observed in the product contract are retained as compatibility aliases:

- `RetailEdge Manager` → `RetailEdgeManager`
- `RetailEdge Branch Manager` → `RetailEdgeBranchManager`
- `RetailEdge Auditor` → `RetailEdgeAuditor`

No new spaced Cashier role is introduced; `RetailEdgeCashier` remains its single internal identity in this checkpoint.

Aliases are not deleted or renamed in this phase. Existing pages and runtime checks that deliberately include both forms continue to work.

## Migration behavior

`retailedge.patches.normalize_retailedge_role_assignments` is additive and idempotent:

1. ensure canonical and known compatibility Role records exist;
2. find User role assignments that use a known compatibility alias;
3. add the corresponding canonical role when it is missing;
4. preserve the compatibility alias assignment.

The patch does not rename Role documents, delete roles, remove user assignments, alter Role Permission Manager data, or mutate accounting documents.

## Desk access

RetailEdge operational roles remain Desk-enabled Frappe roles (`desk_access = 1`) so users remain valid System Users and can access `/app`.

`EdgeSuite Only` versus `Native Desk + EdgeSuite` remains a separate shared EdgeSuite UI access-mode decision. Role normalization must never implement that distinction by setting `desk_access = 0`.

Existing Role records are not rewritten by the normalizer; therefore an administrator's current Role record configuration is not silently mutated during migration.

## Permission safety

This slice does not broaden any Page, Report, DocType, purchasing, accounting, stock, or branch permission. In particular, Professional Purchasing remains limited to its existing ERPNext Purchase/Accounts/System Manager authority; product Manager/Branch Manager roles are not added to it.

Frappe permissions and server-side Company/Branch scope remain authoritative.

## Development rule after this checkpoint

New RetailEdge Python code should use the canonical compact IDs or the helpers in `retailedge.setup_roles` when compatibility with aliases is required. Do not introduce a third spelling or silently switch an existing permission definition to a spaced alias.

A future explicit role-rename programme may retire aliases only after every DocType permission, Page/Report role row, Role Profile, user assignment, integration, migration, and downstream app dependency has been proven safe. That retirement is out of scope here.

## Validation required

Freeze this checkpoint only after the exact head passes:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 install + migrate + full RetailEdge tests;
- governed EdgeSuite UI Candidate Compatibility.

Manual browser/persona QA remains deferred to the consolidated pre-reporting QA phase.
