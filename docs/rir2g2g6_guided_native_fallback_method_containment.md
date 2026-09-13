# RIR2G2G6 — Guided Native Fallback Method Containment

## Goal

Make Business Hub guided dialogs fail closed at every layer when Native Desk fallback is unavailable.

## Context

RIR2G2A already removes native navigation for EdgeSuite-only users, hides native fallback controls where applicable, and guards Business Hub parent `openNative*` handlers. Guided child dialogs also receive `nativeFallbackEnabled`.

Several dialogs hide their “Open Full Form” control correctly but their own `openFullForm()` method can still emit `open-native` if invoked programmatically.

## Required contract

Every governed guided dialog with an `openFullForm()` native fallback must:
- keep its full-form control behind `nativeFallbackEnabled`;
- check `nativeFallbackEnabled` inside `openFullForm()`;
- emit `open-native` only when Native Desk is enabled;
- preserve existing saving/submitting busy-state guards.

Corrected:
- Simple Sales Invoice
- Simple Payment
- Simple Stock Transfer
- Simple Stock Adjustment
- Simple Cash Deposit
- Simple Cash / Bank Transfer
- Simple Cashier Expense

Simple Purchase Invoice already satisfies the contract and remains unchanged.

## Safety rules

- No server API, permission, role or desk-access changes.
- No document creation/submission semantics change.
- No accounting, stock, payment-allocation, cash-custody or expense logic changes.
- No shared EdgeSuite UI runtime changes.
- Authorised Native Desk fallback remains available.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- every governed guided dialog keeps its full-form control capability-gated;
- every `openFullForm()` implementation explicitly checks `nativeFallbackEnabled`;
- each guarded method retains its `open-native` event for authorised fallback.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
