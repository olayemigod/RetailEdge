# Pre-reporting Daily Sales Audit Register read-scope contract

## Business goal

The Daily Sales Audit Register must expose audit rows and derived deposit values only inside the current reader's authorised Company and operational Branch scope. A selected Cashier, POS Profile, status or client-supplied Branch remains a business filter, never an authority source.

## B4B9 scope

This slice covers the shared Daily Sales Audit Register dataset engine used by the native query report, the EdgeSuite Daily Sales Audit page and its bounded export endpoint. It covers Company/Branch predicates, scalar business filters, date predicates and deposit totals derived from scoped parent audit rows.

It does not change Daily Sales Audit context/option searches frozen in B4B5, audit calculations, review statuses, review actions, approval/rejection, Cash Deposit semantics, document lifecycle, provider composition or any mutation workflow.

## Company and permission contract

- Company is mandatory before any register dataset can run.
- The current reader must have native read permission for both the selected Company and RetailEdge Daily Sales Audit.
- The native report opens with the reader's Company default as a required filter.
- Company and Branch must be scalar selections; filter operators cannot replace the authority predicates.

## Branch contract

- The register reuses the hardened B4B5 Daily Sales Audit query-scope applicator.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- Unrestricted readers retain company-wide blank-Branch reads.
- A restricted reader with one allowed Branch and blank Branch resolves to that Branch.
- A restricted reader with multiple allowed Branches and blank Branch reads only their allowed union.
- A restricted reader with zero active Branches receives an impossible predicate and no rows.
- An explicit Branch outside the current reader's allowed Branches fails closed.
- Cashier, POS Profile, Audit Status and Audit Result remain dataset filters and cannot replace the current reader as access principal.

## Child-read and compatibility boundaries

- Deposit totals receive only POS Opening Shift names from already-scoped Daily Sales Audit rows plus the mandatory Company.
- Expected Cash, Cash Variance and Net Variance calculations are unchanged.
- Date presets and manual date filtering are unchanged and are added only after Company/Branch authority is resolved.
- The native report, EdgeSuite page and bounded export all reuse the same hardened register engine.
- The existing shared export-action gate may require a restricted multi-Branch reader to select one Branch before invoking the same bounded export engine.
- No Daily Sales Audit, Payment Entry, Sales Invoice, POS shift, Cashier Expense, stock or accounting document is mutated.
- Reporting development remains blocked.

## Manual QA checklist

1. Restricted reader with one Branch: blank Branch resolves to it and native report, page and export contain only that Branch.
2. Restricted reader with multiple Branches: blank Branch contains only the allowed union; where the shared export-action gate requires it, select one authorised Branch before exporting.
3. Restricted reader with zero active Branches: report, page and export return no rows.
4. Explicit unauthorised Branch: server rejects the native report, page and export request.
5. Unrestricted manager: blank Branch retains company-wide behaviour inside the selected Company.
6. Missing, nonexistent or unreadable Company: the dataset does not execute.
7. Reader without Daily Sales Audit read permission: the dataset is rejected.
8. Cashier/POS Profile/status filters: results remain inside the resolved reader scope.
9. Compare deposits, expected cash and variance values with pre-hardening results inside an authorised scope.
10. Confirm no source document changes after report, page or export reads.
