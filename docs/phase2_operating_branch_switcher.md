# Phase 2 — Operating Branch Switcher

## Business goal

Give each RetailEdge user an explicit **Operating Company** and **Operating Branch** context so new work starts in the correct branch and normal document browsing stays in the selected branch without changing historical document truth. Users with genuine company-wide Branch access may deliberately choose **All Branches** for a Company-wide browsing/reporting view.

The operating context is a user/session convenience and control layer. It is not a new accounting dimension, stock ledger, document owner, or replacement for ERPNext Company/Branch/Warehouse fields.

## Product layer

Phase 2 belongs in RetailEdge today because RetailEdge needs the operating context immediately for guided sales, purchases, payments, stock and POS workflows. The implementation must remain compatible with the long-term CoreEdge context service and keep existing CoreEdge/user-default/Branch Profile resolution as fallback.

## Core contracts

1. Existing submitted or draft documents retain their stored Company, Branch, Warehouse, POS Profile and accounting values.
2. The Operating Branch guides new guided drafts/defaults when the caller has not made an explicit valid selection and scopes normal branch-attributed document lists to the selected Working Branch.
3. Explicit Warehouse/Stock Location remains authoritative when supplied.
4. Branch selection is validated server-side for:
   - Company read permission or equivalent RetailEdge Company authority;
   - Branch read permission or equivalent RetailEdge Branch Assignment authority;
   - Company/Branch association where Branch has a Company field;
   - active/not-disabled Branch state where supported;
   - RetailEdge Branch Assignment/CoreEdge/User Permission branch restrictions;
   - enabled Branch Setup Company→Branch binding whenever Branch Setup history exists for the Company.
5. Branch Setup is the RetailEdge Company→Branch identity/binding authority. Optional operational defaults such as POS Profile, Warehouse, cost centre or accounts may remain blank without hiding an otherwise valid configured Branch.
6. Branch Profile remains the source of RetailEdge operational defaults such as POS Profile, stock locations, cost centres and payment accounts. Missing optional defaults may make POS/default readiness incomplete; a missing/disabled Company→Branch binding does not become valid merely because the user has a Branch Assignment.
7. Existing branch resolvers remain fallback/historical resolvers and are not deleted.
8. A context switch must not silently rewrite an open or historical document.
9. An active POSNext shift or ERPNext POS Opening Entry blocks switching to a different Company/Branch or to All Branches server-side.
10. Unsaved browser-only POS/cart/payment state uses a client guard extension point; provider-specific cart integration is not falsely claimed by this phase.
11. Client-side list scoping is a working-view default, not an authorization boundary. Native Frappe/ERPNext permissions and RetailEdge server-side permission rules remain authoritative.
12. **All Branches** is an explicit Company-wide read/view context, not a blank-Branch authorization shortcut. It is available only when the server confirms unrestricted Branch scope for that Company. Branch-owned writes/posting/stock operations still require a specific valid Branch where the transaction requires one.
13. Broad full-form, POS Profile, report and dashboard default activation belongs to **Phase 3 — Branch defaults & operational context activation**.

## Company-wide view decision note

Current Frappe/ERPNext permission behavior remains the baseline: role permissions define capability and User Permissions narrow records; lack of a Branch restriction does not itself create a new Branch identity. RetailEdge therefore keeps ERPNext/Frappe permissions authoritative and adds no parallel read permission system.

Comparable multi-entity products commonly separate an aggregated management view from the concrete entity used for operational transactions. RetailEdge follows that pattern deliberately:

- `All Branches` is shown only after server-side scope evaluation for the selected Company;
- restricted users never receive the option even if they have more than one Branch Assignment;
- Company remains a hard boundary in company-wide ListView scope;
- entering `All Branches` clears the Working Branch list filter but retains the Company filter;
- new branch-dependent work receives no arbitrary Branch default while company-wide view is active;
- existing document truth remains unchanged;
- open POS work can block the scope change because POS remains branch-specific.

This is the smallest extension of the existing Operating Context model that supports management-wide visibility without weakening Branch Setup, native permissions, accounting or stock governance.

## Delivery slices

### 2A — Operating context service — implemented

- `retailedge/operating_context.py`
- Session-scoped cache keyed by user + Frappe session id.
- 12-hour TTL; clearable without changing Frappe User Defaults.
- APIs:
  - `get_operating_context`
  - `get_allowed_operating_contexts`
  - `switch_operating_context`
  - `switch_company_wide_context`
  - `clear_operating_context`
- Existing user/CoreEdge/default resolver used only when no valid session override exists.
- Company, Branch, Branch Setup company binding and disabled state are validated server-side.
- Active Branch Assignment is authoritative for assignment-managed restricted users; legacy User Permission/Branch Profile user membership remains fallback for users not yet migrated to assignments.
- Branch Setup supplies the Company→Branch binding and optional defaults. Optional defaults may be blank, but the configured binding may not be bypassed by assignment alone.
- Company-wide state is persisted explicitly and revalidated on each recovered session/cache context.
- Previewing another Company's Branch options does not mutate or clear the active context.
- Clearing a session override resolves the fallback first and applies the same POS switch-safety gate before changing context.

### 2B — Guided-entry integration — implemented

- `guided_entry_context.resolve_branch_warehouse_selection` consumes Operating Branch only when Branch and Stock Location are both absent.
- Explicit Company/Branch/Stock Location selections continue to win.
- Branch Profile resolves the correct stock-location preference for sales, purchases, source, target or default use.
- Internal ERPNext `Warehouse` identities and fields remain unchanged.
- In All Branches mode, Company context remains available but no Branch is fabricated for branch-dependent new work.

### 2C — Shell switcher and POS protection — implemented for Phase 2

- Dedicated `Operating Context` Page under RetailEdge Home.
- Current Operating Company/Branch flows into the existing EdgeSuite product profile through the canonical shell identity.
- Company → Branch selection cascades using bounded permission-aware server options.
- Server-authorized unrestricted users receive `All Branches`; restricted users do not.
- Successful switch invalidates the existing Business Hub context cache and refreshes the product menu.
- Server-side switch blockers cover:
  - POSNext `POS Opening Shift`;
  - ERPNext `POS Opening Entry`.
- Client-side `window.retailedgeOperatingContextGuard.getBlocker()` extension point is available for browser-only unsaved cart/payment state. The actual provider-specific cart guard is deferred until the POS integration phase where that state is owned.

### 2D — Working Branch document scope — implemented

- Standard RetailEdge-attributed ERPNext transaction lists use the stored `retailedge_branch` attribution as the normal list scope when a Working Branch is selected.
- RetailEdge branch-owned document lists such as Cashier Expense and Business Expense use their stored `branch` field.
- The scope is applied through Frappe ListView filters before the list request, preserving existing user filters while replacing any stale Branch/Company context filter.
- In All Branches mode, the Branch filter is removed only when the ListView has a Company field that can retain the active Company as a hard boundary.
- Specialized purchase/cashier list customizations compose the same scope instead of replacing it.
- Switching Branch or entering All Branches and reloading the current route changes the normal document set immediately.
- Stored document Branch truth is not rewritten, and the filter is not registered as a server permission query condition.

### 2E — Phase 2 hardening/audit — current gate

- Audit branch/company isolation, fallback behavior, cache/session lifecycle, Page visibility, switch safety, Working Branch/All Branches document scope and multi-app coexistence.
- Lock safety findings with regression tests.
- Run fresh exact-head Linters, clean Frappe v16 CI, upgrade validation, EdgeSuite compatibility and browser persona smoke.

## Deferred to Phase 3 — Branch defaults & operational context activation

Phase 3 will consume the trusted Phase 2 Operating Context more broadly. It should cover, where appropriate:

- full-form new-document defaults;
- branch-specific POS Profile activation and related operational defaults;
- report/dashboard default filters while still allowing authorized users to broaden scope;
- additional branch-aware operational pages and workflows;
- migration/backward-compatibility review for the wider activation layer.

Phase 2 scopes the normal document list view to the active Working Branch, or to the selected Company when an authorized user chooses All Branches. It does **not** change stored historical Branch truth or turn the Working Branch into a replacement authorization model.

## Out of scope

- No Company/Branch field rewrite on existing documents.
- No new accounting dimension.
- No parallel Warehouse/Stock Location DocType.
- No Branch rename or internal ERPNext field rename.
- No automatic submission or posting.
- No CoreEdge package requirement for standalone RetailEdge.
- No server-side permission-query restriction based only on the current Working Branch.
- No cross-Company meaning for `All Branches`.
- No implicit Branch selection for branch-dependent writes while All Branches is active.
- No claim that unsaved POSNext/ERPNext browser carts are detected until the owning POS integration supplies the guard.

## Security and accounting safety

- No `ignore_permissions`.
- No manual database commit.
- No submitted-document mutation.
- Company remains a hard accounting boundary.
- ERPNext Warehouse remains stock truth.
- Branch Setup remains Company→Branch binding authority; Branch Profile optional fields supply operational defaults.
- Client-side list filtering/guards never replace server-side permission or validation.
- Clearing, previewing or entering All Branches cannot be used to bypass Branch/POS safety.

## Tests required

### Unit/static contract

- session key and expiry behavior, including explicit company-wide persistence;
- permission-aware Company/Branch queries;
- disabled/wrong-company/unauthorized Branch rejection;
- configured Branch remains selectable when optional Branch Setup defaults are blank;
- assignment alone cannot bypass Branch Setup Company binding;
- unrestricted user may use company-wide view;
- restricted user may not use company-wide view;
- fallback resolver preservation;
- safe default-context restore;
- explicit selection precedence;
- Branch Profile default projection;
- Working Branch list filter uses stored branch attribution and preserves other ListView filters;
- All Branches removes stale Branch scope only while retaining a Company boundary;
- POSNext and ERPNext POS switch blockers;
- no broad `ignore_permissions`, manual commit or accounting-document mutation.

### Integration

- multi-Branch restricted user sees every permitted active Branch but not All Branches;
- unrestricted user sees All Branches for the selected Company;
- switch then new guided Sales Invoice resolves branch sales stock location when configured;
- switch then Purchase Invoice resolves receiving stock location when configured;
- switch then Stock Transfer resolves source/target defaults correctly when configured;
- switch Branch A → Branch B and representative document lists show Branch B-attributed documents rather than Branch A documents;
- switch to All Branches and representative lists remove stale Branch filter while retaining Company scope;
- invalid branch/company combination blocked;
- unauthorized branch blocked;
- configured Branch with blank optional defaults remains available;
- missing/disabled Branch Setup Company binding remains blocked even when assigned;
- clear context restores configured fallback only when switch-safe;
- multi-company user switches only to permitted company/branch combinations;
- active POSNext/ERPNext POS session allows same-context use but blocks cross-context/company-wide switch.

### Manual browser QA

- current Company/Branch visible in shell;
- Company → Branch cascade;
- all permitted active Branches appear in the Working Branch switcher;
- All Branches appears only for an unrestricted user and is labeled clearly;
- selecting All Branches removes the Branch ListView filter but leaves the selected Company filter;
- restricted users cannot activate company-wide mode by UI or direct API;
- invalid dependent Branch clears on Company change;
- switch refreshes guided-create defaults without reload surprises;
- Sales/Purchase/Stock/Payment document lists immediately follow the selected Working Branch or authorized Company-wide scope;
- existing open and historical documents remain unchanged;
- branch-specific guided stock-location defaults are respected when configured;
- active POS session blocks cross-branch/company-wide switching;
- client guard behaves correctly once an owning POS integration provides browser-state evidence;
- mobile/responsive picker behavior;
- multi-app shell remains stable.

## Phase closure

Phase 2 closes only after exact-head automated validation and browser/persona verification prove the permission-aware Branch option set, All Branches governance and document-list scope without weakening native permission enforcement.
