# Pre-reporting dashboard capability Branch-scope contract

## Business goal

RetailEdge dashboard view, print and export capability checks must use the current reader's authorised Company and operational Branch scope. Client-provided Company and Branch values are selections, never authority.

## B4B17 scope

This slice replaces the shared dashboard capability layer's residual legacy Branch helper and Branch-count convention with the assignment-aware operational scope authority. It applies to capability discovery and the existing view, print and export gates only. It does not change dashboard datasets, calculations, routes, feature settings, role matrices, reference-document permission checks, file composition or mutations.

## Company and Branch contract

- An explicit Company still requires Company read permission before Branch scope is resolved.
- A Branch without its Company is rejected because assignment and Company→Branch membership cannot be validated safely.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback through the operational scope helper.
- An explicit Branch outside the current reader's active restricted scope is rejected before Company→Branch validation.
- An authorised or unrestricted explicit Branch is revalidated against Company→Branch setup.
- A restricted reader with zero active Branches fails closed, including at dashboard shell capability discovery.
- A restricted reader with one or more active Branches may load a dashboard shell before choosing a Branch. This grants no data scope: each dashboard backend remains responsible for applying its own hardened Company/Branch dataset authority.
- An unrestricted reader retains established blank-Branch Company-wide dashboard capability behavior.

## Preserved composition

- View, print and export remain independent role-and-setting capabilities.
- Reference DocType read permission remains part of dashboard view authorization.
- Print and export services continue to recheck the shared capability gate before building output.
- Dashboard datasets remain the authority for their own scoped rows, summaries and calculations.
- No capability check reads dashboard data or mutates ERPNext/RetailEdge documents.
- Manual browser/persona QA remains a separate deferred gate and is not inferred from automation.

## Manual QA checklist

1. Restricted reader with one active Branch: dashboard shell loads, that Branch can be selected, and the dashboard backend returns only scoped data.
2. Restricted reader with multiple active Branches: shell loads unselected; each authorised Branch works independently and an unauthorised Branch is rejected.
3. Restricted reader with zero active Branches: shell, view, print and export capability checks fail closed.
4. Reader with Company permission denied: capability discovery fails before Branch resolution.
5. Branch supplied without Company: capability discovery fails closed.
6. Unrestricted manager with blank Branch: existing Company-wide dashboard capability behavior remains available.
7. Confirm view, print and export roles/settings remain independent and unchanged.
8. Confirm dashboard file generation rechecks the same Company/Branch gate before reading the dataset.
9. Confirm dashboard rows, summaries, calculations, filters and navigation remain behaviorally unchanged.
10. Confirm no Company, Branch, transaction or configuration document is mutated.
