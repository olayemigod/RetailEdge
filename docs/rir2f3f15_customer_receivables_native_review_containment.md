# RIR2F3F15 — Customer Receivables Native-Review Containment

## Goal

Keep Customer Receivables as an EdgeSuite reporting surface while preventing users without final Native Desk capability from opening native receivable documents or creating Payment Request/Dunning drafts that require native ERPNext review.

## Context

Customer Receivables already uses permission-aware, branch-safe, submitted/current-outstanding accounting truth. Its collection actions call backend methods that revalidate invoice scope, native create/read permissions, duplicate state, and draft-only behavior before preparing Payment Request or Dunning documents.

The remaining gap is interface exposure: the page does not currently read final Native Desk capability, native document columns are always clickable, and collection actions can POST a native draft even when the user cannot enter ERPNext Desk to review it.

## Scope

- `retailedge/public/js/customer_receivables/CustomerReceivablesReport.vue`
- focused frontend contract tests
- this contract document

## Out of Scope

- receivables calculations or ageing
- Sales Invoice mutation
- Payment Request/Dunning backend constructors
- collection posting/submission
- branch/company authorization logic
- duplicate detection
- ERPNext permissions
- accounting/GL semantics
- schema, migrations, patches, or data

## Implementation Requirements

1. Add fail-closed `canUseNativeDesk: false`.
2. Populate it from `navigation.access.can_use_native_desk` after the final navigation context resolves.
3. Sales Invoice, Customer, Payment Request, and Dunning detail columns are clickable only when Native Desk capability is true.
4. `payment_request_action` and `dunning_action` columns are appended only when Native Desk capability is true.
5. `prepareCollectionAction()` must return before any POST when Native Desk is unavailable.
6. `openReportCell()` must fail closed before native detail or collection-action routing when Native Desk is unavailable.
7. `handleNavigation()` must block DocType/Report routes without Native Desk capability.
8. Native-Desk-capable users retain the current draft preparation and native review behavior.
9. Do not change backend accounting, duplicate, branch, permission, or draft-only safeguards.

## Safety Rules

- No submitted Sales Invoice mutation.
- No weakening of backend branch or permission enforcement.
- No frontend-only replacement for backend authorization.
- No unreachable native draft should be created for an EdgeSuite-only user.
- No new accounting or collection model.

## Tests Required

Focused tests must verify:

- Native Desk capability fails closed and comes from final navigation context;
- native detail columns are capability-gated;
- collection action columns are capability-gated;
- collection actions fail before the POST when Native Desk is unavailable;
- DocType/Report menu routes fail closed;
- native detail routing remains present for allowed users;
- backend collection safety files are not semantically changed by the slice.

## Freeze Rule

Mark F3F15 `CODE-FROZEN / QA-PENDING` only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and governed EdgeSuite UI Candidate Compatibility pass on the exact implementation head. Browser/persona QA remains separately required for full freeze.
