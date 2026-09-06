# Pre-reporting Action Follow Up direct-read scope contract

## Business goal

Direct list, report and form reads of RetailEdge Action Follow Up records must expose only records inside the current reader's authorised Company, operational Branch and owner-financial scope. The Action Centre's scoped fingerprint lookup remains the normal product path, but native direct access must be equally safe.

## B4B19 scope

This slice replaces the direct-read permission hooks' legacy Branch-only convention with Company-specific, assignment-aware reporting scope. It covers permission query conditions and individual document read checks only. It does not change Action Centre composition, follow-up decoration, status logic, assignments, update APIs, write guards, prioritization, routes or business-document resolution.

## Direct-list contract

- The reader must hold an Action Centre role before any follow-up row can be listed.
- Company candidates come from a bounded, permission-aware Company query and are rechecked for the requested reader.
- Each readable Company is resolved independently through the hardened reporting Branch authority.
- Restricted Companies contribute only clauses for active allowed Branches; restricted-zero or unresolved Companies contribute no clause.
- Unrestricted Companies retain Company-wide Branch behavior, but only inside that Company.
- R9 early-warning follow-ups are included within a Company/Branch clause only when the reader also has owner-dashboard financial access for that exact scope.
- If no safe Company/Branch clause can be resolved, the query returns `1=0`.
- Administrator retains the established unrestricted permission-hook behavior.

## Direct-form contract

- Action Centre role and Company read permission are mandatory.
- A missing Company fails closed.
- Restricted readers must have an active assignment to the record's nonblank Branch.
- Restricted-zero, blank-Branch and out-of-scope Branch records fail closed.
- Unrestricted readers retain Company-wide access within readable Companies.
- R9 early-warning records additionally require owner-financial access for the record's exact Company/Branch.

## Preserved composition

- Fingerprint generation and scoped decoration reads are unchanged.
- Follow-up status, acknowledgement, snooze, assignment and schedule behavior are unchanged.
- Update APIs still re-resolve the visible Business Control Centre item before writing.
- Controller-level direct-write guards remain unchanged.
- No Action Follow Up read resolves or mutates an accounting, stock or other business document.
- Manual browser/persona QA remains deferred and is not inferred from automation.

## Manual QA checklist

1. Restricted reader with one active Branch: native list/form access exposes only that Company's assigned-Branch follow-ups.
2. Restricted reader with multiple active Branches: native list exposes the union of only those active Branches in each readable Company.
3. Restricted reader with zero active Branches: native list is empty and direct form access is denied.
4. Reader without Company permission: no follow-up row for that Company appears and direct form access is denied.
5. Unrestricted manager: Company-wide follow-ups appear only for readable Companies.
6. Operational manager without owner access: ordinary follow-ups appear, while R9 early-warning follow-ups remain hidden.
7. Owner-authorised reader: R9 follow-ups appear only in the exact Company/Branch scopes where owner capability succeeds.
8. Confirm Action Centre fingerprint decoration still resolves the same follow-up state for visible items.
9. Confirm acknowledge, snooze, assign, schedule and reopen behavior is unchanged.
10. Confirm no underlying accounting, stock or operational document is changed by list/form reads.
