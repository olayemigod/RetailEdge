# RIR2F3F10 — Recurring Billing Native Fallback Containment

## Decision

ERPNext `Subscription` and `Subscription Plan` remain the recurring-billing system of record, but their RetailEdge Money navigation entries are classified as deliberate `native_fallback` routes.

RetailEdge does not currently provide an EdgeSuite subscription-management workspace. This slice therefore does not claim operational ownership that does not exist and does not build a second recurring-billing engine.

## Business goal

Keep everyday RetailEdge navigation EdgeSuite-first without removing legitimate advanced recurring-billing capability from users who are explicitly allowed to use Native Desk.

## Scope

- Mark **Subscriptions** (`Subscription`) as `native_fallback` in the Money navigation group.
- Mark **Subscription Plans** (`Subscription Plan`) as `native_fallback` in the Money navigation group.
- Continue to rely on the existing EdgeSuite access context to hide native fallbacks when Native Desk is unavailable.
- Continue to rely on ERPNext DocType permissions when Native Desk is available.
- Preserve Payment Management, Payment Reconciliation, bank statement import and Bank Matching ownership exactly as currently composed.

## Out of scope

- New Subscription or Subscription Plan DocTypes.
- A RetailEdge subscription ledger.
- An EdgeSuite recurring-billing workspace.
- Changes to ERPNext subscription invoice generation, schedules, billing dates, cancellation, accounting, GL, tax, payment allocation or document lifecycle.
- New role definitions or permission overrides.
- Migration or patch work.

## Safety rules

1. ERPNext remains the recurring-billing authority.
2. No submitted accounting document may be mutated by this slice.
3. Native fallback visibility must remain controlled by the existing `can_use_native_desk` access contract.
4. ERPNext read permissions remain authoritative for users who can use Native Desk.
5. Do not add a RetailEdge-specific subscription state or shadow ledger.

## Expected behaviour

### EdgeSuite-only user

- Does not see **Subscriptions** or **Subscription Plans** in RetailEdge navigation.
- Continues to use the existing RetailEdge everyday Money surfaces.

### Native-Desk-authorized user

- May see the two recurring-billing routes when ERPNext permissions permit them.
- Opens the native ERPNext Subscription/Subscription Plan experience deliberately as an advanced fallback.

## Follow-up

A future recurring-billing product slice may introduce a dedicated EdgeSuite owner if subscription workflows become an explicit RetailEdge MVP/business requirement. Such a slice should first define customer lifecycle, plan setup, billing schedule, exception handling, branch/company scope, invoice review and cancellation semantics before retiring the native fallback.
