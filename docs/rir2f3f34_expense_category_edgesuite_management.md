# RIR2F3F34 — Expense Category EdgeSuite Management

## Goal

Complete the F3F25 ownership correction for Expense Categories.

RetailEdge Expense Category is a RetailEdge-owned master used by Business Expenses, Cashier Expenses and expense reporting. Normal setup work therefore belongs inside RetailEdge Setup rather than a routine native DocType list/form handoff.

## System of record

RetailEdge Expense Category remains the system of record.

F3F34 does not introduce a duplicate category table, mirror document or parallel validation model.

The existing DocType controller remains authoritative for:

- valid Expense Account root type;
- leaf/non-group Expense Account validation;
- disabled-account rejection;
- Company consistency;
- leaf Cost Centre validation;
- Cost Centre Company consistency;
- required fields and naming rules.

The EdgeSuite manager guides the user and then saves the same DocType through normal Frappe document APIs.

## Permission boundary

F3F34 does not broaden DocType permissions.

The manager:

- requires normal read permission before loading;
- exposes create only when Frappe create permission exists;
- exposes edit only when the selected document grants write permission;
- uses normal permission-aware `frappe.get_list` queries;
- revalidates Company, Account and Cost Centre read permission server-side;
- does not use `ignore_permissions`;
- does not manually commit.

The RetailEdge Setup Page remains subject to its existing Page roles.

## RetailEdge Setup ownership

The Expense Categories setup resource declares:

`manager = "expense-categories"`

RetailEdge Setup uses that metadata to open an in-page EdgeSuite manager.

This applies to:

- View Records;
- Add New;
- existing route handoff using `frappe.route_options.setup_resource = "expense-categories"`;
- direct edit handoff using `expense_category`;
- optional manager action `setup_action = "new"`.

The normal Expense Category path no longer opens the native list/new form.

Other RetailEdge Setup resources remain unchanged in this slice and may continue to use their existing Page or native advanced setup paths.

## Bounded list

Expense Categories are loaded through a permission-aware bounded service.

Supported filters are:

- Company;
- Active / Inactive / All;
- search text across name, category name, category code and description.

Pagination is bounded to a maximum configured page size.

The matching scan is capped at 1,000 records. If more records match, RetailEdge requires narrower filters rather than loading an unbounded master.

## Smart create/edit form

The EdgeSuite manager supports:

- Category Name;
- Category Code;
- Company;
- Expense Account;
- Default Cost Centre;
- Active state;
- Description;
- Notes.

New EdgeSuite-created categories require an explicit Company.

This requirement exists so dependent accounting choices are always resolved inside an unambiguous Company context.

Legacy categories without Company can still be inspected/edited according to existing permissions and DocType validation.

## Dependent accounting choices

Expense Account search requires Company first and returns only:

- the selected Company;
- `root_type = Expense`;
- non-group ledger accounts;
- non-disabled accounts.

Default Cost Centre search requires Company first and returns only:

- the selected Company;
- non-group Cost Centres.

When Company changes or is cleared, the form clears:

- Expense Account;
- Default Cost Centre.

Frontend filtering is guidance only. Server-side save independently revalidates link permissions and Company consistency before the existing DocType controller validates the document.

## Concurrency

Edit saves are stale-`modified` protected.

If the document changed after the user opened it, RetailEdge blocks the save and requires a reload instead of silently overwriting another user's change.

## Category identity

Category Name is the current autoname source for RetailEdge Expense Category.

To avoid an accidental master-key rename hidden inside ordinary edit, the EdgeSuite manager treats Category Name as stable after creation.

An actual category rename remains an explicit administrator/advanced operation outside this bounded manager.

Category Code, accounting defaults, active state, description and notes remain editable subject to normal permissions.

## Deactivation instead of delete

F3F34 does not add a delete action.

A category that should no longer be selected operationally can be marked inactive.

Existing references and historical transactions therefore retain their category identity.

## Accounting safety

Expense Category is setup/master data only.

No accounting document is created or mutated by F3F34.

The slice does not:

- create Journal Entry;
- create or edit GL Entry;
- create Purchase Invoice;
- change Cashier Expense posting;
- change Business Expense posting or reversal;
- alter submitted accounting documents;
- create Account or Cost Centre records.

## Migration and compatibility

No schema migration is required.

The existing RetailEdge Expense Category DocType, names, records, controller and native advanced form remain intact.

F3F34 only changes the normal EdgeSuite setup ownership path and adds permission-aware APIs/UI for managing the same records.

## Tests required

Focused contract coverage verifies:

- Setup metadata declares the Expense Category manager;
- bounded permission-aware list reads;
- create/write permissions remain native-Frappe authoritative;
- stale edit protection;
- stable Category Name during EdgeSuite edit;
- explicit Company on new EdgeSuite categories;
- Company-dependent Expense Account search;
- Company-dependent Cost Centre search;
- Company changes clear dependent values;
- server-side link permission and Company validation;
- route-options enter the in-page manager;
- View Records and Add New do not launch the native Expense Category route;
- list/create/edit/activation behavior;
- no delete action;
- no permission bypass or accounting mutation.

The four governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. Expense Categories opens inside RetailEdge Setup;
2. route from Expense Review/Expense Register opens the same manager;
3. Add Category remains in EdgeSuite;
4. Company is mandatory for a new category;
5. Expense Account remains empty/unsearchable until Company is selected;
6. Expense Account results contain only valid leaf Expense accounts for that Company;
7. Cost Centre results contain only leaf Cost Centres for that Company;
8. changing Company clears both dependent fields;
9. cross-Company Account is blocked server-side;
10. cross-Company Cost Centre is blocked server-side;
11. inactive category can be reactivated;
12. active category can be deactivated;
13. Category Name cannot be silently renamed through ordinary edit;
14. stale edit is rejected;
15. read-only user cannot create/edit;
16. ordinary category management never opens the native DocType form/list;
17. unrelated Setup resources retain their previous behavior.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope

- permission-role redesign;
- bulk category import/export;
- category merge;
- automated master rename;
- Account creation;
- Cost Centre creation;
- native-form elimination for unrelated Setup resources;
- expense workflow changes;
- accounting posting changes.
