# Pre-reporting guided invoice Branch scope

This checkpoint extends the frozen B3 operational Branch-scope contract from guided Stock Transfer to guided Sales Invoice and guided Purchase Invoice.

## Authority

- Branch Assignment history remains authoritative when it exists.
- Sites/users without Branch Assignment history retain the established legacy Branch validation path for explicit Branch values.
- Blank Branch writes use the explicit Operating Context operational-scope resolver so an empty allowed-branch list cannot be mistaken for unrestricted access.
- ERPNext/Frappe document permissions remain authoritative in addition to the RetailEdge operating-scope checks.

## Restricted-user behavior

For a restricted user within a selected Company:

- exactly one active permitted Branch may resolve automatically;
- multiple permitted Branches require explicit Branch selection before Warehouse search or draft creation;
- zero active permitted Branches fail closed;
- Branch option searches return no permitted destination when the active scope is empty;
- Warehouse searches never broaden from blank Branch to every Warehouse in the Company for restricted users;
- any selected Warehouse is revalidated against Company and the resolved Branch before the draft is inserted.

Unrestricted/advanced users retain the existing Company-wide blank-Branch behavior.

## Scope

This slice changes only:

- guided Sales Invoice context/search/write Branch handling;
- guided Purchase Invoice context/search/write Branch handling;
- focused regression coverage for the shared operational-scope behavior.

It does not change invoice pricing authority, taxes, accounts, payment schedules, stock/accounting posting semantics, submission behavior, native ERPNext permissions, roles, or submitted documents.

Both flows still create ordinary ERPNext draft Sales Invoice/Purchase Invoice documents as the current user. There is no `ignore_permissions`, automatic submit, GL/SLE posting, submitted-document mutation, or manual database commit.
