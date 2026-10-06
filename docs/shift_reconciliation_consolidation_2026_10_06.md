# RetailEdge Shift Reconciliation Consolidation

Date: 2026-10-06

## Business goal

Reduce cashier/supervisor review clutter by giving RetailEdge one clear cash-control front door for a POS shift while preserving the specialist workflows that still perform real review mutations.

The canonical customer-facing surface is **Shift Reconciliation**.

## Phase 1 implemented

- Keep the stable internal route `pos-closing-variance` for backward compatibility, but present it as **Shift Reconciliation**.
- Use the existing **RetailEdge Cash Shift Verification** dataset as the authoritative cash-reconciliation source.
- Present the shift cash equation through operational fields:
  - Opening Cash
  - Cash Sales
  - Till Expenses
  - Cash Deposits
  - Expected Cash
  - Counted Cash
  - Cash Variance
  - Cash Status
  - Audit Status
- Remove the standalone **Cash Shift Verification** and duplicate **Daily Sales Audit Register** entries from normal Review & Approvals navigation when the user is permitted to open Shift Reconciliation.
- Keep **Daily Sales Audit** visible because it still owns sales-audit review/approval workflow.
- Keep **Cashier Expense Review** visible because it still owns expense include/exclude/clarification workflow.
- Keep all legacy routes directly routable so bookmarks, historical links and controlled fallback paths continue to work.
- If a user does not have permission to the canonical Shift Reconciliation page, preserve the already permission-filtered legacy navigation instead of hiding their available fallback.

## Cash and accounting rule

Shift reconciliation is operational cash truth, not a replacement for ledger truth.

Cashier expenses can affect expected till cash according to existing RetailEdge settings even when their accounting workflow is not yet posted. This is intentional because cash may already have physically left the till. Approval, posting and ledger status remain separate accounting/governance concerns.

This slice does not mutate submitted ERPNext accounting documents, change posting logic, or introduce a schema migration.

## Backward compatibility

- Internal page name remains `pos-closing-variance`.
- Existing query reports and legacy pages remain installed.
- No DocType rename.
- No database patch required.
- Existing permissions remain authoritative.

## Next safe phases

1. Add context-aware Branch -> POS Profile -> Cashier filtering to the consolidated surface using the existing Cash Shift Verification scoped search methods.
2. Add direct drill-through from a shift row to its Daily Sales Audit and filtered Expense Register / Expense Review context.
3. Absorb the remaining Daily Sales Audit and Cashier Expense Review mutation actions into Shift Reconciliation only after feature and permission parity is proven.
4. Once parity is proven, remove those specialist pages from everyday navigation while retaining safe historical/direct access where still required.
5. Browser QA across cashier, branch manager, accounts and auditor personas before merge.

## Manual QA checklist

- Review & Approvals shows Shift Reconciliation instead of separate Cash Shift Verification and Daily Sales Audit Register entries for a manager who can open the canonical page.
- Daily Sales Audit and Cashier Expense Review remain available.
- Shift Reconciliation loads with expected cash, counted cash, till expenses, cash deposits and variance.
- A balanced shift shows zero variance.
- A till expense reduces expected cash according to the configured cash-check policy.
- A submitted cash deposit reduces expected cash once, without double counting.
- Company and Branch permission scope is respected.
- A role without access to Shift Reconciliation retains its permitted fallback navigation.
- Direct legacy route links continue to resolve.
