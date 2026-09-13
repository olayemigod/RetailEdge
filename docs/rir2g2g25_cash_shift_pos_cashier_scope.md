# RIR2G2G25 — Cash Shift Verification POS Profile → Cashier Option Scope

## Goal

Complete the Cash Shift Verification Company → Branch → POS Profile → Cashier smart-form cascade by making Cashier options respect the selected POS Profile while preserving the existing cash-shift read-scope authority.

## Gap

Cash Shift Verification already validates Company/Branch through `resolve_cash_shift_verification_read_scope`, and its POS Profile/Cashier searches are derived from permission-aware Daily Sales Audit records inside that scope.

However:
- the active page does not pass the selected POS Profile to option search;
- selecting/clearing POS Profile does not clear Cashier;
- Cashier search is Branch-scoped but not POS-Profile-scoped, so a Cashier seen on another profile in the same Branch can remain selectable.

## Required contract

### POS Profile
- Existing Company/Branch-scoped POS Profile search remains unchanged.
- A selected POS Profile is never trusted from the browser; it must still exist in the already-authorised Daily Sales Audit scope before it may constrain Cashier options.

### Cashier
- Cashier search remains permission-aware, enabled-User bounded, and Daily-Sales-Audit-derived.
- When POS Profile is selected, candidate Cashiers must come only from authorised Daily Sales Audit rows matching that POS Profile inside the current Company/Branch scope.
- Invalid or out-of-scope POS Profile produces no Cashier options.
- Blank POS Profile preserves the existing Branch-scoped Cashier search.

### Frontend cascade
- Option search passes Company, Branch and POS Profile.
- Selecting POS Profile clears Cashier and its label.
- Clearing POS Profile clears Cashier and its label.
- Existing Company/Branch cascades remain unchanged.

## Out of scope

- Cash Shift Verification calculations, status logic, unsynced-invoice detection, report provider, sorting, pagination, export, native-detail containment or Daily Sales Audit workflow.
- POS Profile or User master changes.
- Branch Assignment/read-scope changes.

## Safety

- No submitted-document mutation.
- No `ignore_permissions`.
- No manual commit.
- No new access authority; existing cash-shift read scope remains authoritative.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
