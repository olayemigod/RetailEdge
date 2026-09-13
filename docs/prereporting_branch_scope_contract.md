# Pre-reporting operational Branch scope contract

## Purpose

RetailEdge operational writes must distinguish a genuinely unrestricted user
from a restricted user who currently has zero permitted Branches. An empty
Branch list is therefore never interpreted on its own.

This B3 checkpoint introduces the explicit operational scope contract at the
Operating Context layer and applies it first to guided Stock Transfer. It does
not change ERPNext Stock Entry posting or submission behaviour.

## Authority and compatibility

The precedence is:

1. A user with global Branch access remains unrestricted.
2. Once RetailEdge Branch Assignment history exists, active Branch Assignments
   filtered through enabled Branch Setup and native read visibility are
   authoritative.
3. Without Branch Assignment history, legacy Branch User Permission, default
   Branch and Branch Profile restrictions remain the compatibility fallback.
4. A legacy user with no configured Branch restriction retains the existing
   Company-wide blank-Branch behaviour.

`get_operational_branch_scope()` returns `restricted` independently from
`allowed_branches`. Consequently, assignment history with no active permitted
Branch returns `restricted = true` and `allowed_branches = []`; it does not
broaden to Company-wide access.

## Guided Stock Transfer rules

For both source and target Branch:

- an explicit Branch is revalidated through Operating Context;
- a blank Branch resolves automatically only when exactly one Branch is
  permitted for the Company;
- multiple permitted Branches require an explicit choice;
- zero permitted Branches fail closed;
- unrestricted users retain the existing Company-wide blank-Branch behaviour.

Branch search returns only the authoritative permitted Branch set for a
restricted user. Warehouse search is unavailable until Company is known and,
for a multi-Branch restricted user, until the corresponding Branch is chosen.

On draft creation, source and target warehouses are revalidated server-side:

- each Warehouse must exist and be readable by the current user;
- each Warehouse must belong to the selected Company;
- when Branch-restricted, each Warehouse must be linked to its resolved Branch
  through the native Branch field or active RetailEdge Branch Setup defaults.

Frontend filtering is guidance only and is not treated as authorization.

## Preserved ERPNext behaviour

- Stock Entry remains the transaction source of truth.
- The guided flow creates a normal draft Material Transfer as the current user.
- ERPNext continues to own item defaults, valuation, validation, submission and
  Stock Ledger posting.
- No document is submitted automatically.
- No submitted document is mutated.
- No `ignore_permissions`, manual commit, GL write or SLE write is introduced.

## Deferred scope

This checkpoint does not migrate Purchase Invoice, Sales Invoice, Payment
Management, Customer Receivables or other audited workflows. They may consume
the same Operating Context contract in later separately tested slices after the
guided Stock Transfer checkpoint is frozen.
