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

## Phase 2 implemented

- Make Shift Reconciliation filters cascade as **Company -> Branch -> POS Profile -> Cashier**.
- Reuse the existing permission-aware Daily Sales Audit option search for Branch, POS Profile and Cashier instead of loading unrestricted database values.
- Clear only dependent values when a parent selection changes:
  - Company clears Branch, POS Profile and Cashier.
  - Branch clears POS Profile and Cashier.
  - POS Profile clears Cashier.
- Make the **Shift** cell open Daily Sales Audit already filtered to the selected shift's company, branch, POS profile, cashier and date.
- Make a non-zero **Till Expenses** cell open Expense Review filtered to the shift's company, branch, cashier and date.
- Make the top **Open Sales Audit Review** action carry the current Shift Reconciliation filters into Daily Sales Audit.
- Teach Daily Sales Audit to consume this route handoff and remove the old customer-facing reference to the legacy register.
- Keep drill-through inside EdgeSuite-facing workflow surfaces; normal users are not pushed into native ERPNext forms.

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

1. Browser-QA the consolidated surface across cashier, branch manager, accounts and auditor personas, including Branch -> POS Profile -> Cashier option scope.
2. Verify shift drill-through for balanced, shortage, overage, expense and deposit scenarios.
3. Decide whether Daily Sales Audit review actions should be embedded directly into Shift Reconciliation or remain a deliberate secondary workflow for MVP.
4. Decide whether Cashier Expense Review actions should be embedded directly into Shift Reconciliation or remain a deliberate secondary workflow for MVP.
5. Only after feature/permission parity is proven, remove any remaining specialist workflow page from everyday navigation while retaining safe historical/direct access where required.

## Manual QA checklist

- Review & Approvals shows Shift Reconciliation instead of separate Cash Shift Verification and Daily Sales Audit Register entries for a manager who can open the canonical page.
- Daily Sales Audit and Cashier Expense Review remain available.
- Shift Reconciliation loads with expected cash, counted cash, till expenses, cash deposits and variance.
- Company selection limits Branch options; Branch limits POS Profile; POS Profile limits Cashier.
- Changing Company clears Branch/POS Profile/Cashier; changing Branch clears POS Profile/Cashier; changing POS Profile clears Cashier.
- Clicking a Shift opens Daily Sales Audit with the same shift date and operating context.
- Clicking a non-zero Till Expenses amount opens Expense Review with the same shift date, branch and cashier context.
- A balanced shift shows zero variance.
- A till expense reduces expected cash according to the configured cash-check policy.
- A submitted cash deposit reduces expected cash once, without double counting.
- Company and Branch permission scope is respected.
- A role without access to Shift Reconciliation retains its permitted fallback navigation.
- Direct legacy route links continue to resolve.
