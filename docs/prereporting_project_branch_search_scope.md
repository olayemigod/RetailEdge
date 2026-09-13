# Pre-reporting Project Branch option-search scope contract

## Business goal

The Project Operations Branch selector must never broaden to every readable Branch when the current user has Branch Assignment history but no active Branch for the selected Project Company. The Company chosen from the permission-aware Project search is the mandatory scope boundary for Branch options.

## B4B22 scope

This slice hardens only `search_project_branches`. It replaces the legacy empty-list/global-role interpretation with the explicit operational Branch scope already used by RetailEdge smart operational forms. It does not change Project search, Project Operations datasets, Project totals, timelines, budgets, receipts, expense routing, documents, or mutations.

## Option-search contract

- Branch read permission remains mandatory.
- A selected Company is mandatory; a missing Company returns no Branch options.
- The current reader must have Company read permission before scope or Branch candidates are resolved.
- Branch Assignment history remains authoritative through `get_operational_branch_scope`.
- Restricted-zero access returns no options and performs no Branch candidate query.
- Restricted single/multi access is intersected with enabled Company Branch Profiles when those profiles are readable.
- If Branch Profiles are unavailable, restricted candidates remain limited to the explicit allowed Branch list.
- An empty Company/Profile intersection returns no options rather than removing the Branch filter.
- Unrestricted global and compatible unrestricted legacy readers retain bounded, permission-aware Branch lookup behavior.
- Text search is applied only within the already-authorized candidate set.

## Preserved composition

- `search_projects` remains the permission-aware ERPNext Project selector.
- Project Operations continues to request Branch options only after a Project Company is known.
- Changing Project still clears stale Branch state in the EdgeSuite component.
- Project funds, activities, budgets, receipts and spend/material routes remain unchanged.
- ERPNext Projects and documents remain the transaction and accounting authority.
- Business Hub and reconciled QA composition remain unchanged.

## Deferred manual QA

Browser/persona validation remains part of the reconciled manual QA pass. Verify the Branch selector as an unrestricted manager, unrestricted legacy user, restricted single-Branch user, restricted multi-Branch user, restricted-zero user and Company-denied user. Confirm changing Project clears the selected Branch and does not change Project Operations data or actions.
