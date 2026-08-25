# Phase 2 — Operating Branch Switcher

## Business goal

Give each RetailEdge user an explicit **Operating Company** and **Operating Branch** context so new work starts in the correct branch without changing historical document truth.

The operating context is a user/session convenience and control layer. It is not a new accounting dimension, stock ledger, document owner, or replacement for ERPNext Company/Branch/Warehouse fields.

## Product layer

Phase 2 belongs in RetailEdge today because RetailEdge needs the operating context immediately for guided sales, purchases, payments, stock and POS workflows. The implementation must remain compatible with the long-term CoreEdge context service and keep existing CoreEdge/user-default/Branch Profile resolution as fallback.

## Core contracts

1. Existing submitted or draft documents retain their stored Company, Branch, Warehouse, POS Profile and accounting values.
2. The Operating Branch guides **new** drafts/defaults only when the caller has not made an explicit valid selection.
3. Explicit Warehouse/Stock Location remains authoritative when supplied.
4. Branch selection is validated server-side for:
   - Company read permission;
   - Branch read permission;
   - Company/Branch association where Branch has a Company field;
   - active/not-disabled Branch state where supported;
   - RetailEdge/CoreEdge/User Permission branch restrictions.
5. Allowed Company/Branch options are permission-aware and bounded; do not preload unrelated masters.
6. Branch Profile remains the source of RetailEdge operational defaults such as POS Profile, stock locations, cost centres and payment accounts.
7. Existing branch resolvers remain fallback/historical resolvers and are not deleted.
8. Reports may default to the operating branch, but an authorized user may deliberately broaden or change report scope.
9. A context switch must not silently rewrite an open document.
10. POS/cart/payment state must block an unsafe branch switch once the client/runtime integration is wired.

## Delivery slices

### 2A — Operating context service

- `retailedge/operating_context.py`
- Session-scoped cache keyed by user + Frappe session id.
- 12-hour TTL; clearable without changing user defaults.
- APIs:
  - `get_operating_context`
  - `get_allowed_operating_contexts`
  - `switch_operating_context`
  - `clear_operating_context`
- Existing user/CoreEdge/default resolver used only when no valid session override exists.

### 2B — Guided-entry integration

- `guided_entry_context.resolve_branch_warehouse_selection` consumes Operating Branch only when Branch and Stock Location are both absent.
- Explicit Company/Branch/Stock Location selections continue to win.
- Branch Profile resolves the correct stock-location preference for sales, purchases, source, target or default use.

### 2C — Shell switcher and POS protection

Planned on this same PR:

- Product-menu Operating Context action/picker.
- Current Company/Branch shown in the product profile.
- Refresh Business Hub context after switch.
- Client-side unsafe-switch guard for active guided drafts and POSNext/ERPNext POS cart/payment state.
- Server retains permission validation even when client guard passes.

### 2D — Report/default integration and hardening

Planned on this same PR after 2C:

- Permission-aware report default context where the report currently derives a branch default.
- Preserve deliberate user filter changes.
- Audit context-sensitive API surfaces for branch/company isolation.
- Automated and manual QA.

## Out of scope

- No Company/Branch field rewrite on existing documents.
- No new accounting dimension.
- No parallel Warehouse/Stock Location DocType.
- No Branch rename or internal ERPNext field rename.
- No automatic submission or posting.
- No CoreEdge package requirement for standalone RetailEdge.
- No broad report enforcement that prevents authorized users from broadening scope.

## Security and accounting safety

- No `ignore_permissions`.
- No manual database commit.
- No submitted-document mutation.
- Company remains a hard accounting boundary.
- ERPNext Warehouse remains stock truth.
- Branch Profile only supplies defaults; ERPNext document validation remains authoritative.
- Client-side filtering/guards never replace server-side validation.

## Tests required

### Unit/static contract

- session key and expiry behavior;
- permission-aware Company/Branch queries;
- disabled/wrong-company/unauthorized Branch rejection;
- fallback resolver preservation;
- explicit selection precedence;
- Branch Profile default projection;
- no broad `get_all`, `ignore_permissions`, manual commit or accounting-document mutation.

### Integration

- switch then new guided Sales Invoice resolves branch sales stock location;
- switch then Purchase Invoice resolves receiving stock location;
- switch then Stock Transfer resolves source/target defaults correctly;
- invalid branch/company combination blocked;
- unauthorized branch blocked;
- clear context restores configured fallback;
- multi-company user switches only to permitted company/branch combinations.

### Manual browser QA

- current company/branch visible in shell;
- Company → Branch cascade;
- invalid dependent Branch clears on Company change;
- switch refreshes guided-create defaults without reload surprises;
- existing open document remains unchanged;
- branch-specific POS Profile/stock locations are respected;
- active POS cart/payment blocks branch switching;
- mobile/responsive picker behavior;
- multi-app shell remains stable.

## Phase closure

Phase 2 may continue implementation while predecessor browser QA is pending. It must remain a stacked Draft PR and must be reconciled against the promoted predecessor before Phase 2 manual QA/promotion if that predecessor moves.
