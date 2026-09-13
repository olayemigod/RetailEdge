# RIR2 F3F6 — Money → Payments Navigation Ownership

## Goal

Make the normal RetailEdge **Money → Payments** navigation open the EdgeSuite-owned **Payment Management** page rather than the native ERPNext Payment Entry list.

F3F1–F3F5 already established Payment Management as the everyday RetailEdge surface for guided customer receipts, supplier payments, Business Hub payment actions, customer settlement/advance handling, and generic Payment Entry history/revisit. Keeping the primary Money → Payments item on native Payment Entry would bypass that completed product experience.

## Scope

- Change only the **Payments** navigation item in `retailedge/edgesuite_ui.py`.
- Route it to the Frappe Page `payment-management`.
- Preserve its label, icon, navigation group and normal visibility semantics.
- Keep the existing Payment Management EdgeSuite-only operational guard authoritative.
- Keep native Payment Entry access as an explicit, permission-gated advanced fallback inside Payment Management where already supported.

## Out of Scope

- Payment Reconciliation ownership or workflow changes.
- Payment Order ownership or workflow changes.
- Changes to customer/supplier payment creation, review or submit services.
- Changes to Payment Entry posting, GL Entry, Payment Ledger Entry or reconciliation semantics.
- New DocTypes, schema changes, patches or migrations.
- CoreEdge runtime or installation requirements.

## Safety Rules

1. ERPNext Payment Entry remains the accounting source of truth.
2. Submitted or cancelled accounting documents must not be mutated.
3. Payment Reconciliation remains a native ERPNext DocType navigation item in this slice.
4. Payment Orders remain a native ERPNext DocType navigation item in this slice.
5. The change must remain on the reconciled PR #55 branch; do not create a divergent implementation line.
6. Freeze only an exact head that passes all four governed RetailEdge gates.

## Expected Behaviour

For a user who can open the RetailEdge Payment Management Page:

- **Money → Payments** opens `payment-management`.
- Payment Management owns the normal payment experience and history/revisit path.
- Native Payment Entry is not the primary navigation destination.
- Advanced native access remains available only where the existing permission-aware fallback allows it.

For this checkpoint, **Payment Reconciliation** and **Payment Orders** continue to open their existing native ERPNext destinations.

## Migration / Compatibility

No database migration is required. Existing Payment Entries, permissions, accounting data and posting behaviour are unchanged. The change is navigation-only and can be reversed independently if required.
