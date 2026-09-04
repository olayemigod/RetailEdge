# Pre-reporting Daily Sales Audit read-scope contract

## Business goal

Daily Sales Audit must let an authorised reviewer inspect a cashier, POS Profile, opening shift, closing shift, invoices, payments, and cashier expenses without allowing the selected cashier to become the security principal. The reviewer’s own Company/Branch operating access remains authoritative for every read.

## Scope

This B4B5 hardening covers Daily Sales Audit context resolution, smart option lists, cashier search, POS Profile search, and POS opening/closing shift search.

It does not change audit calculations, review statuses, approval/rejection behaviour, posting, Sales Invoice lifecycle, Payment Entry lifecycle, Stock Entry lifecycle, or any submitted accounting document.

## Branch access contract

RetailEdge uses the operational Branch contract established during prereporting hardening:

- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the legacy Branch User Permission/default/profile compatibility fallback.
- Unrestricted/advanced readers may retain blank Branch for company-wide reads.
- A restricted reader with one allowed Branch may resolve blank Branch to that Branch.
- A restricted reader with multiple allowed Branches may use the union for option/search reads, but a singular Daily Sales Audit must resolve to a valid Branch before transactional reads begin.
- A restricted reader with zero allowed Branches receives no operational options and cannot open a singular audit context.
- An explicit or inferred Branch outside the current reader’s allowed Branches fails closed.

## Cashier and context safety

The selected cashier is a business subject only. It may still be used to identify cashier-specific shifts and cash calculations, but it never determines the current reviewer’s Branch permission.

A Branch inferred from a cashier, POS Profile, POS Opening Shift, or POS Closing Shift is revalidated server-side against the current session user before invoices, payments, cashier expenses, or shift cash are read.

## Smart-form behaviour

- Branch options are restricted to the current reader’s permitted Branches for the selected Company.
- POS Profiles are scoped through Branch-aware profile or shift context.
- Cashier options are derived from scoped operational POS context; the search endpoint does not fall back to every enabled User.
- Opening and closing shift searches use the same current-reader Branch scope.
- Operational selectors do not become cross-company queries when Company context is missing.

Frontend filtering remains a usability feature only. Server-side validation is authoritative.

## Backward compatibility

- Unrestricted/advanced users retain company-wide blank-Branch behaviour.
- Cashier-specific `get_shift_cash_snapshot(..., user=<selected cashier>)` semantics are preserved because that argument describes the business subject of the cash calculation, not the reader’s access authority.
- Existing Daily Sales Audit calculations, exception logic, review workflow, child-line review actions, and document lifecycle are unchanged.
- No migration patch or database schema change is required.

## Manual QA checklist

1. Restricted reviewer, one Branch: select Company and confirm only that Branch and its operational POS context are available.
2. Restricted reviewer, multiple Branches: confirm Branch options show only allowed Branches; confirm an audit cannot proceed with an unresolved singular Branch.
3. Restricted reviewer, zero active Branches: confirm Branch/POS/cashier/shift options are empty and audit context fails closed.
4. Attempt an explicit unauthorised Branch and confirm server-side denial.
5. Select a cashier or shift belonging to an unauthorised Branch and confirm the inferred Branch is rejected for the reviewer.
6. Confirm POS Profile and cashier searches do not expose records outside allowed Branches.
7. Confirm unrestricted manager behaviour remains company-wide when Branch is blank.
8. Confirm shift cash, invoice/payment totals, cashier-expense totals, variance calculations, and review actions match pre-hardening behaviour for an authorised Branch.
9. Confirm no source Sales Invoice, Payment Entry, Stock Entry, POS shift, or Cashier Expense is mutated by read/context operations.
