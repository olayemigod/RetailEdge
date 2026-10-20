# MVP-C1 User Readiness Research — 2026-10-20

## Scope

Issue #199 is the final material RetailEdge MVP capability: an administrator must be able to determine whether a RetailEdge operational user is actually ready to work, repair incomplete setup deliberately, and prevent incomplete users from being treated as unrestricted simply because no Branch restriction exists yet.

This slice does **not** introduce a second identity, permission, Branch, POS, accounting, stock, or user-default system. It orchestrates existing Frappe/ERPNext and RetailEdge authority.

## Current supported platform baseline

The repository candidate is pinned by `platform-baseline.json` to:

- Frappe 16.52.0
- ERPNext 16.51.1
- EdgeSuite UI 1.1.0
- Python 3.14
- Node 24

The manifest is still `candidate` with manual `retail.local` QA required, so this feature must be validated on a new exact release candidate before 1.0 promotion.

## Frappe / ERPNext baseline findings

### Identity and authorization

Frappe's native permission model already owns User identity, roles, DocType permissions, Role Permission Manager, and User Permissions. User Permissions additionally narrow records through linked values. RetailEdge should therefore validate readiness against these native authorities instead of creating a parallel ACL.

Sources:

- https://docs.frappe.io/framework/user/en/basics/users-and-permissions
- https://docs.frappe.io/framework-git/security/permission-model
- https://docs.frappe.io/framework-git/security/user-permissions

Frappe v16 also supports custom Permission Types for action-specific rights. They are intentionally **not** used for this slice because user readiness is an orchestration/state problem, not a new business action permission.

Source:

- https://docs.frappe.io/framework/permission-types

### POS applicability

ERPNext POS Profile already has a native per-user applicability table. Once users are specified on a POS Profile, other users cannot use that profile, and one profile can be marked default for a user. RetailEdge should preserve this model and verify it when POS has been explicitly assigned rather than inventing a RetailEdge POS-user mapping.

Source:

- https://docs.frappe.io/erpnext/pos-profile

## Mature retail comparator

Shopify POS separates staff identity, POS role/permissions, and location access. Staff can be assigned specific retail locations, while permissions decide what they may do. This supports the same separation in RetailEdge: native User/roles define capability, explicit Branch Assignment defines operational location scope, and POS Profile applicability remains a distinct POS concern.

Sources:

- https://help.shopify.com/en/manual/sell-in-person/shopify-pos/staff-management
- https://help.shopify.com/en/manual/sell-in-person/shopify-pos/staff-management/understanding-pos-staff-management

## Existing RetailEdge authority to reuse

The repository already has the required primitives:

- `RetailEdge Branch Assignment` with effective dates and preserved transfer history;
- explicit Company → Branch validation against enabled Branch Setup;
- one primary Branch per overlapping Company period;
- Operating Context with Branch Assignment authority and restricted-zero semantics once assignment history exists;
- Branch Setup / `RetailEdge Branch Profile` defaults;
- ERPNext `POS Profile User` applicability;
- canonical RetailEdge roles and aliases;
- EdgeSuite Branch Assignments and Operating Context pages.

The missing piece is a single readiness contract that composes these authorities and a reconciliation surface for incomplete users.

## Chosen design

1. Add a reusable server-side readiness service.
2. A RetailEdge-role user is ready only when the user is an enabled System User and has active explicit Branch Assignment coverage for the requested Company.
3. Active assignments must resolve to enabled Branch Setup, minimum native Company/Branch read authority, and—where native POS applicability exists—a compatible enabled POS Profile assigned to that user.
4. Multiple active Branches in one Company require one Primary Branch so the starting Branch is deterministic.
5. Administrator is not subject to operational readiness. Users without a RetailEdge product role are outside this contract.
6. Global RetailEdge manager authority may remain Company/Branch-wide **after** readiness is established. A primary assignment is an initial operating anchor; it must not narrow legitimate global management scope.
7. Incomplete users must fail closed for RetailEdge operational entry. Setup-capable administrators/managers must retain a repair route.
8. Reconciliation is read-only: no migration or report may silently create Branch Assignments, User Permissions, POS mappings, or defaults.
9. Existing historical users remain unchanged until an administrator explicitly repairs them.
10. The existing EdgeSuite Branch Assignments page is the preferred repair surface; no duplicate user/branch master is introduced.

## Deliberately rejected approaches

- Auto-assigning a Branch from a Company default, Branch Setup default, POS Profile, latest invoice, or first visible Branch.
- Treating absence of Branch restrictions as unrestricted for a user carrying a RetailEdge operational role.
- Creating a RetailEdge-specific role/permission engine parallel to Frappe.
- Rewriting historical Branch Assignments to make a user ready.
- Requiring CoreEdge for standalone RetailEdge 1.0.
- Building a new POS user mapping instead of ERPNext `POS Profile User`.

## Required validation

At minimum this slice must cover:

- ready single-Branch user;
- expired-only assignment;
- assignment in another Company;
- multiple active Branches without deterministic Primary Branch;
- global RetailEdge manager readiness without narrowing valid global scope;
- optional non-POS user;
- POS-assigned user with missing/mismatched/disabled POS setup;
- incomplete-user reconciliation without mutations;
- browser acceptance for a ready user and an intentionally incomplete user;
- exact-head CI, linters, upgrade validation, EdgeSuite compatibility, theme, and Browser Persona gates before merge/release promotion.

## PR #235 CI continuation

Failed head `370fb674adafafdadc6b93058f2b7d2708e02663`, run `39429028480`, job `118649243662` exposed missing native Company read for the cashier acceptance persona. The same defect removes the ready cashier's Home navigation in the browser gate. Frappe's pinned `v16.52.0` `frappe/installer.py` defaults `install_app(..., set_as_patched=True)` and records application patches complete without executing them. RetailEdge already owns an idempotent cashier Company read/select repair, but unlike the management and Stock Manager repairs it was absent from `after_migrate`.

Reuse that existing repair in the migration hook after role creation. Do not weaken readiness, add accounting authority, or create Branch Assignments/User Permissions. The isolated cashier acceptance setup also invokes the same repair, verifies readiness and Company read without write, and retains its negative Journal Entry authority assertions. A negative readiness regression proves that an assignment cannot substitute for native Company read.

Two source contracts also became stale when readiness added a sibling Vue mount and server-owned repair labels. Assert the separate notice/hub mount targets and teardown, and test the server repair key/label independently of the Vue binding. Existing browser acceptance exercises the actual label and ready/incomplete-user behavior.

Primary framework source: https://github.com/frappe/frappe/blob/v16.52.0/frappe/installer.py

The first browser continuation passed 54 existing cases but its Playwright `testMatch` excluded `user_readiness`, despite the workflow naming that file. Include the readiness spec in discovery and verify that all three readiness journeys appear in the executed run. Scope the administrator's repair assertions to the intended incomplete user's row, since other incomplete users and assignment history are valid simultaneous page content.

The enabled acceptance then confirmed that expired-only assignment history denies an explicitly requested Company with HTTP 403 in `get_allowed_operating_contexts`, before Branch enumeration. Preserve that existing governance: test the explicit denial separately from the unselected switcher's empty Company/Branch lists and incomplete-readiness guidance. Do not change production access rules to satisfy an incorrect HTTP 200 expectation.

## Late automated-review corrections

The automated review started when draft PR #235 was marked ready and completed after the merge, finding two valid UI defects. Corrections are prepared on the same feature branch: explicitly invoke the general assignment action and accept only string User prefill values; retain server `total`/`has_more` metadata and append subsequent readiness pages through a Load More Users action. The existing EdgeSuite runtime has no standalone pager primitive; this uses its existing button styling without introducing a product-local pagination component. Disable the include-ready toggle during requests so an appended page cannot mix different views.

Behavioral regressions cover a click-event argument, deliberate repair prefill, 205 users across three pages, and resetting a changed view to its first page. Browser regression assertions distinguish the prefilled repair dialog from the blank general assignment dialog. These corrections have not been merged: GitHub cannot reopen the merged PR, and the user's no-new-PR constraint requires explicit authorization before creating a correction PR. The previously green head's evidence does not validate this additional candidate.
