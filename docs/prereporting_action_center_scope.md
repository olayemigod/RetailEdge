# Pre-reporting Action Centre read-scope contract

## Business goal

The Action Centre must compose every operational exception source inside one current-reader Company and Branch scope. Stored defaults and client filters are selections, never authority.

## B4B18 scope

This slice replaces Action Centre's residual legacy Branch resolution with the shared assignment-aware reporting scope authority. It covers context defaults, explicit/implicit Branch resolution and the scope passed to the existing composite sources and read-only follow-up decoration. It does not change source calculations, prioritization, routes, follow-up mutations, assignment rules, business workflows or dashboard composition.

## Company and Branch contract

- Company remains mandatory before Action Centre data is composed.
- Company read permission and Branch scope are validated through the hardened reporting scope authority.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established User Permission/default/Branch Profile compatibility fallback through the shared helper.
- A valid selected/default Branch is revalidated against Company→Branch setup.
- A stale or unauthorised restricted default is removed; exactly one active allowed Branch is selected only when unambiguous.
- A restricted reader with one active Branch is safely narrowed to that Branch before any source is called.
- A restricted reader with multiple active Branches must select a Branch before data composition.
- A restricted reader with zero active Branches fails closed before any source is called.
- An unrestricted reader retains established blank-Branch Company-wide behavior.

## Composite-read boundary

- Stock, expense, cash-shift, receivables, payables, bank-control, customer-sales and planning sources receive the same resolved Company/Branch scope.
- Each source remains responsible for its own hardened permissions and query authority.
- A source-specific permission/validation failure remains isolated and does not expose its payload.
- Follow-up decoration reads only the fingerprints created from the already-scoped action population.
- Deduplication, prioritization, summary cards and follow-up filtering remain unchanged.
- No Action Centre read creates, submits, updates or resolves an ERPNext/RetailEdge business document.

## Manual QA checklist

1. Restricted reader with one active Branch and no default: context and data auto-narrow to that Branch.
2. Restricted reader with multiple active Branches and no valid selection: data fails closed with the existing Branch-selection message.
3. Restricted reader with zero active Branches: context/data cannot reach any source loader.
4. Stale or unauthorised default Branch: it is removed and replaced only by one unambiguous active Branch.
5. Valid authorised default: it is preserved after Company→Branch revalidation.
6. Unrestricted manager with blank Branch: existing Company-wide Action Centre behavior remains available.
7. Confirm every available source receives the same resolved Company/Branch values.
8. Confirm a denied source appears only as unavailable and does not expose payload details.
9. Confirm ordering, priority reasons, summaries, fingerprints and follow-up filters remain unchanged.
10. Confirm follow-up actions and underlying accounting/stock/business documents are not changed by the read-scope slice.
