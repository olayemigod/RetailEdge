# RetailEdge EdgeSuite Master Workspace — Phase 2

## Business goal

Extend the RetailEdge Setup Workspace with two frequently maintained RetailEdge masters:

1. RetailEdge Expense Category
2. RetailEdge Statement Mapping Template

The purpose is to give managers a consistent EdgeSuite setup experience without replacing ERPNext accounting truth, bypassing native permissions, or creating a second master-data model.

## Product layer

This work belongs in RetailEdge because both masters define RetailEdge operational behaviour:

- Expense Category controls how cashier expenses are classified and which expense ledger/cost centre may be suggested.
- Statement Mapping Template controls how bank, POS settlement and mobile-money statement columns are interpreted during imports.

EdgeSuite UI supplies the shared presentation components only. RetailEdge remains responsible for the resource allowlist, permissions, validation and business-specific Link filtering.

## Resources added

### Expense Categories

The workspace provides:

- permission-aware list, search and pagination;
- Company and Active filters;
- create and draft edit through normal Frappe `insert()` / `save()`;
- Company-aware Expense Account and Cost Center Links;
- Expense Account restricted to non-group accounts with Root Type `Expense`;
- Cost Center restricted to non-group records;
- backend rejection of cross-company, group or non-expense ledger selections.

Changing Company clears Expense Account and Default Cost Center so stale accounting defaults cannot survive a context change.

### Statement Mapping Templates

The workspace provides:

- permission-aware list, search and pagination;
- Company, Enabled, Statement Type and Payment Category filters;
- create and draft edit through normal Frappe `insert()` / `save()`;
- Company-aware Default Account lookup;
- non-group account enforcement;
- backend rejection of cross-company or group account selections.

Changing Company clears Default Account.

## Provider generalisation

Phase 1 supported only Branch Profiles and the single RetailEdge Settings document. Before adding new masters, the provider was corrected so that:

- Branch list filters are applied only to the Branch Profile resource;
- Branch scope checks are applied only to Branch Profile reads and saves;
- other resources rely on normal Frappe list, document and User Permission enforcement;
- resource-specific validation runs through an explicit allowlisted dispatcher;
- unsupported resource names remain blocked.

This prevents invalid Branch filters from being injected into DocTypes that have no Branch field.

## Smart form behaviour

The shared metadata-driven form continues to honour:

- Tab Break, Section Break and Column Break layout;
- mandatory, read-only and visibility dependencies;
- Link field permissions;
- field-level cascade clearing;
- server-side validation after frontend filtering;
- optimistic modified-timestamp checks.

Company-scoped Link fields return no broad results until a Company context is available. This avoids loading every Account, Warehouse or Cost Center in the database.

## Safety boundaries

This phase does not expose:

- generic access to arbitrary DocTypes;
- deletion;
- submission or cancellation;
- workflow transitions;
- Journal Entry or Payment Entry creation;
- GL Entry creation;
- Sales Invoice mutation;
- Bank Transaction reconciliation;
- stock document writes;
- POS shift writes.

Native DocType controllers, validations, naming rules, permissions and User Permissions remain authoritative.

## Migration and backward compatibility

No DocType fields, database tables, patches or data migrations are introduced.

Existing native routes remain available:

- `/app/retailedge-expense-category`
- `/app/retailedge-statement-mapping-template`
- `/app/retailedge-branch-profile`
- `/app/retailedge-settings`

The EdgeSuite workspace is an additional interface, not a replacement of native Frappe forms.

## Automated tests

Tests cover:

- the four-resource allowlist;
- exclusion of operational/accounting DocTypes;
- runtime resource discovery;
- Company cascade clearing;
- Expense Account Root Type and group filtering;
- resource-specific Branch list scoping;
- resource-specific named-document Branch checks;
- backend account validation contracts;
- existing Branch Profile permission query conditions;
- optimistic locking;
- absence of submit, cancel, delete and accounting-posting operations.

## Manual QA gate

Manual QA is deferred until full CI can install the shared EdgeSuite UI dependency.

Before merge, validate:

1. Expense Category list/search/filter and native fallback.
2. Expense Category create/edit with Company, Expense Account and Cost Center cascades.
3. Rejection of group, non-expense and cross-company accounts.
4. Statement Mapping Template list/search/filter and native fallback.
5. Statement Mapping Template create/edit and Company-to-Default Account cascade.
6. Role-based read/create/write behaviour.
7. Responsive list and form layouts.
8. Optimistic conflict handling after another user edits the same record.

## CI dependency

The RetailEdge repository still requires the GitHub Actions secret `EDGESUITE_UI_TOKEN` with read-only Contents access to `olayemigod/processedge-edge-suite-ui`.

Until that secret is available, full CI stops before bench setup, asset build, migration and Frappe tests. The shared dependency must not be bypassed with copied assets, duplicated EdgeSuite components or a CI-only fake app.
