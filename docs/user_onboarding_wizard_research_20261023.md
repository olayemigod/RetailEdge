# RetailEdge User Onboarding Wizard Research — 2026-10-23

## Scope

Build a guided RetailEdge user-onboarding experience without creating a second identity, role, Branch, POS, permission or readiness authority.

The wizard must support both new and existing Users, make POS optional, preserve current Branch Assignment history/governance, and finish by evaluating the existing User Readiness contract.

## Supported platform baseline

This slice is designed against the RetailEdge candidate baseline:

- Frappe 16.52.0 — `4515014c87ece6cb20ee91d2cfb121c5cbd1ff4a`
- ERPNext 16.51.1 — `5af6561f5aa48104559692fb4fd82f2580e8d338`
- EdgeSuite UI 1.1.0 — `d50920b005da8dcf1bd1e35c1c88be8afedecfbf`

The separate runtime-compatibility release candidate in PR #238 remains frozen and is not modified by this feature branch.

## Frappe / ERPNext baseline findings

### User and role authority

Frappe `User` remains the identity authority. Frappe derives `System User` capability from roles with Desk access, validates Role Profiles, and owns DocType/record permissions. The wizard therefore creates or edits the native User and assigns only one of RetailEdge's canonical product roles. It does not create a parallel user record or merchant-specific ACL.

RetailEdge's canonical product roles are:

- `RetailEdgeCashier`
- `RetailEdgeManager`
- `RetailEdgeBranchManager`
- `RetailEdgeAuditor`

Business-document permissions such as Sales, Accounts, Stock and Purchasing remain merchant-governed through ERPNext/Frappe roles, Role Permission Manager, User Permissions and sharing. The wizard does not silently grant them.

### Role Profiles

Frappe Role Profiles are authoritative role bundles. If an existing User is governed by a Role Profile that does not contain the requested RetailEdge role, the wizard fails closed and asks the administrator to update the Role Profile rather than appending a role that Frappe would later remove during Role Profile reconciliation.

### ERPNext POS applicability

ERPNext `POS Profile.applicable_for_users` is the native per-user applicability authority.

Important native semantic: an empty Applicable for Users table means the POS Profile is shared. Adding the first user row would change the profile from shared to restricted and could silently remove access from other staff. RetailEdge therefore preserves an empty/shared table and does not add the first restriction during onboarding.

When the table is already restricted, the wizard may add the selected User or make their existing row the default, using the native POS Profile document and its controller validation. ERPNext continues to validate the default-profile relationship.

POS is conditional. A User who does not need Point of Sale must not be marked incomplete merely because they do not have a POS Profile assignment, and the onboarding operator does not need POS Profile read/write authority for a non-POS User.

### Welcome email

Frappe's native User controller owns welcome/reset-password email generation. New Users are inserted with automatic welcome email disabled; the wizard invokes the native welcome method only after the governed RetailEdge setup has completed and User Readiness reports Ready. A mail-delivery failure is reported separately from the already-completed access setup.

## Existing RetailEdge authority reused

The wizard composes existing services rather than replacing them:

- `RetailEdge Branch Assignment` and its effective-dated history;
- Company -> Branch validation through enabled `RetailEdge Branch Profile` / Branch Setup;
- Branch Assignment role and Primary Branch governance;
- permission-aware Branch Assignment searches;
- canonical RetailEdge roles;
- ERPNext POS Profile applicability;
- `get_retailedge_user_readiness` as the final readiness contract.

An exact active Branch Assignment may be reused. If the User already has a different active Branch in the same Company, the wizard stops and routes the administrator to Branch Assignments rather than silently transferring or rewriting history.

## EdgeSuite / native UI findings

The pinned EdgeSuite UI exposes the semantic primitives required by this flow:

- `EdgeLinkField` for User, Company and Branch;
- `EdgeDropdown` for fixed access/responsibility choices;
- `EdgeInput` for email/name and individual date input;
- `EdgeCheckbox` for Primary Branch, welcome-email and POS choices;
- shared loading/status primitives.

The pinned EdgeSuite version does not expose a dedicated wizard/stepper primitive. The smallest safe implementation therefore composes the supported primitives into a local progress shell inside RetailEdge Setup rather than introducing another product-neutral component in this slice.

Company -> Branch cascading is mandatory: changing Company clears Branch and reloads permission-aware Branch options.

## Comparator / workflow practice

Mature retail systems separate staff identity, role/capability and location access. RetailEdge follows the same principle while retaining ERPNext/Frappe governance:

**Person -> RetailEdge access -> Company/Branch operating scope -> optional POS applicability -> readiness.**

The wizard is an orchestration layer, not a new authority.

## Chosen first implementation

Host **User Onboarding** inside the existing RetailEdge **Setup** hub with five business-facing stages:

1. **Person** — existing User or new User.
2. **Access** — canonical RetailEdge role and Branch responsibility.
3. **Location** — Company -> Branch, effective date and Primary Branch.
4. **Point of Sale** — explicit optional POS requirement.
5. **Review** — apply the governed changes and show final User Readiness.

The completion endpoint is POST-only and revalidates the selected Company/Branch/POS setup server-side before consequential writes.

## Deliberate non-goals

This slice does not:

- create User Permissions;
- set User default Company or Branch;
- invent a RetailEdge POS-user table;
- grant broad ERPNext transaction roles;
- silently transfer an existing Branch Assignment;
- rewrite assignment history;
- replace User Readiness;
- change the frozen PR #238 release candidate.

## Required validation

Automated coverage must verify at least:

- payload validation and canonical role restriction;
- non-POS flow does not require POS mutation;
- shared POS Profile remains shared;
- restricted POS Profile uses the native child table;
- exact existing Branch Assignment reuse does not require create permission;
- different active Branch blocks silent transfer;
- Role Profile fail-closed behavior;
- no User Permission/default/ignore-permissions shortcut in the onboarding service;
- Setup integration and five-stage UI contract;
- Company change clears Branch;
- dark/theme-safe shared primitives;
- exact-head RetailEdge CI, lint, upgrade, EdgeSuite compatibility and browser persona gates;
- manual `retail.local` acceptance before release promotion.
