# Pre-reporting native visual workspace scope contract

## Goal

Prevent RetailEdge native visual workspaces from displaying one operating Company/Branch while their bounded DocType previews silently show records from another operating context.

This hardening is deliberately limited to the read-only DocType previews served by `retailedge.native_visual_workspaces`. It does not change accounting documents, ERPNext permissions, report execution, native Desk access, or any write workflow.

## Authoritative context

`get_native_visual_workspace` resolves the current server-side RetailEdge operating context through `get_operating_context()` once per request.

The same resolved Company and Branch are used for:

- the Company/Branch returned to the EdgeSuite workspace; and
- every context-aware DocType preview filter in that response.

The client does not send Company or Branch values to this endpoint, so forged browser parameters cannot widen the preview scope.

## Preview scope classes

Every DocType preview declares one of the following scope classes.

### `company`

Use when the ERPNext record itself has authoritative Company ownership.

Current examples:

- Budget
- Cost Center
- Asset
- Loyalty Program

The server requires an operating Company and an actual `company` field on the DocType. If either is unavailable, the preview fails closed and returns no rows instead of dropping the Company filter.

### `configured_branch_stock`

Use only when a record can be safely limited through stock-location truth attached to the exact enabled RetailEdge Branch Profile.

Current example:

- Serial No

The server requires an operating Company and Branch, loads only the exact enabled `Company + Branch` profile, and collects its configured default, source, destination and returns stock locations. The Serial No preview is then limited to those warehouses. If the exact Branch Profile or configured stock locations are missing, the preview fails closed.

This does not attempt to infer a Branch from a broad warehouse name or from client state.

### `native_permission`

Use for masters whose ownership is genuinely global or cannot be safely attributed to the operating Branch from authoritative stored fields.

Current examples include:

- Warranty Claim and maintenance masters in this read-only workspace
- Sales Person and Sales Partner
- Asset Category
- Batch
- Price List, Item Price, Pricing Rule, Promotional Scheme and Coupon Code

These sources remain governed by normal Frappe read permission and any source-specific filters. RetailEdge does not invent Company/Branch ownership for them.

`Batch` is intentionally not treated as branch-owned because one batch can have quantity across multiple warehouses. A branch-level batch availability view belongs in a stock-ledger/warehouse-aware query, not a misleading filter on the Batch master.

## Query safety

The existing read contract is preserved:

- `frappe.get_list` remains the preview read path, so normal Frappe permissions still apply;
- each preview remains capped at 12 rows;
- existing source filters are preserved, then authoritative operating-context restrictions are applied on top;
- no `get_all`, `ignore_permissions`, database write, submit, stock ledger or GL behavior is introduced;
- missing schema/context needed for a declared restricted scope fails closed rather than broadening.

The response exposes `scope`, `scope_state`, and an optional `scope_message` for each DocType preview so later EdgeSuite presentation work can explain why a preview is intentionally empty without weakening the server rule.

## Backward compatibility

No DocType schema or fixture migration is required. Existing workspace routes and native handoffs remain unchanged.

The behavioral change is limited to context-aware preview rows and the source of the displayed operating Company/Branch: both now use the session-scoped RetailEdge operating context instead of separate user-default reads.

## Out of scope

This slice does not:

- scope native ERPNext Query Reports opened from these workspaces;
- change report/export APIs elsewhere in RetailEdge;
- normalize RetailEdge role-name aliases;
- add client-side filtering;
- change Branch Profile setup semantics;
- alter native Desk access or `EdgeSuite Only` access mode;
- claim browser/persona QA completion;
- resume reporting development.

Those remain separate pre-reporting gates.

## Regression coverage

`test_prereporting_native_visual_scope.py` covers:

- explicit supported scope declaration for every DocType preview;
- Company filtering while preserving static filters;
- fail-closed behavior when Company attribution is unavailable;
- native-permission-only sources receiving no invented context filter;
- exact Branch Profile warehouse deduplication and Serial No filtering;
- fail-closed behavior when Branch stock setup is missing;
- continued use of server operating context, permission-aware `frappe.get_list`, and the 12-row preview cap.

## Validation gate

Freeze this B3 slice only after the exact final PR head passes:

1. Theme Compatibility
2. Linters / pre-commit / Semgrep / dependency audit
3. clean Frappe v16 install + migrate + full RetailEdge tests
4. governed EdgeSuite UI candidate compatibility

Manual browser QA remains deferred to the consolidated persona QA phase.
