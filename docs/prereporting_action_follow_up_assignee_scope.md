# Pre-reporting Action Follow Up assignee-scope parity contract

## Business goal

The bounded assignee search and backend validation must make the same decision for the same user, Company, Branch and financial scope. A candidate offered by the search must never be accepted through weaker legacy Branch logic, and a valid assignment-aware candidate must not be rejected only because the two paths use different scope authorities.

## B4B20 scope

This slice introduces one shared assignee-scope decision used by `get_assignable_users` and `_validate_assignment_user`. It replaces their residual legacy Branch checks with the hardened reporting scope authority. It does not change Action Centre composition, follow-up fingerprints, status transitions, item re-resolution, persistence fields, controller write guards, prioritization, routes, business-document workflows or Business Hub composition.

## Assignee contract

- Candidates must still be enabled System Users with an Action Centre role.
- Company is mandatory before a candidate can be eligible.
- Company read permission and explicit Branch access are evaluated for the candidate user, not the assigning user.
- Branch Assignment history is authoritative when it exists; legacy User Permission/default/Branch Profile behavior remains the compatibility fallback through reporting scope.
- An explicit Branch is revalidated against Company→Branch setup and the candidate's active scope.
- A restricted candidate cannot own a blank-Branch Company-wide follow-up.
- Company-level follow-ups requiring global scope accept only a candidate whose resolved reporting scope is unrestricted for that Company.
- R9 early-warning assignments additionally require owner-dashboard financial capability in the exact Company/Branch scope.
- Missing Company, restricted-zero scope, inactive/out-of-scope Branch, owner denial and required-global denial all fail closed.

## Preserved composition

- Candidate enumeration remains a bounded, permission-aware `User` query.
- Search text, enabled/System User filters and pagination caps are unchanged.
- The update API still re-resolves the visible Business Control Centre item before assignment.
- Acknowledge, snooze, schedule, assign and reopen state transitions are unchanged.
- Follow-up changes remain separate from resolution of the underlying accounting, stock or operational condition.
- Manual browser/persona QA remains deferred and is not inferred from automation.

## Manual QA checklist

1. Candidate with one active assigned Branch: appears for that Branch and can be assigned successfully.
2. Candidate outside the selected Branch: is absent from search and is rejected if submitted directly.
3. Candidate with Branch Assignment history but zero active Branches: is absent and rejected.
4. Candidate without Company read permission: is absent and rejected.
5. Restricted candidate for a blank-Branch Company-level follow-up: is absent and rejected.
6. Unrestricted candidate for a Company-level follow-up: appears and can be assigned.
7. R9 follow-up candidate without owner capability: is absent and rejected.
8. R9 follow-up candidate with exact Company/Branch owner capability: appears and can be assigned.
9. Confirm search text and pagination still return only enabled System Users with Action Centre roles.
10. Confirm assignment changes only follow-up state and never resolves or mutates the underlying business condition.
