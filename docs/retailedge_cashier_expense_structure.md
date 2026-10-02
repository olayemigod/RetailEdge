# RetailEdge Cashier Expense Structure Reset

> Historical foundation note. The items described below were the scope of the structural reset phase. Cashier autofill, POS shift linkage, merchant-governed approval, Journal Entry posting, POS closing integration and accounting-readiness behavior are now implemented. See `cashier_expense_pos_policy.md` for the current executable policy.

RetailEdge Cashier Expense was recreated as a clean structural foundation after the earlier implementation became difficult to save, list, and maintain safely.

## What This Phase Includes

- A normal `RetailEdge Expense Category` DocType
- A normal `RetailEdge Cashier Expense` DocType
- Stable list-view configuration
- Workspace links for both DocTypes
- Basic structure tests for create/save/list behavior

## Historical Phase Boundary

The structural reset itself did not include autofill, approval, posting, or role-specific workflow rules. Those capabilities were added in later phases.

Current accounting policy is intentionally **Journal Entry only** for Cashier Expense. Payment Entry is not an alternative expense-posting voucher.

## Product Direction

Expense Category exists so cashiers can choose a friendly category instead of selecting an accounting expense account directly. Current workflow, posting, POS and merchant-governance behavior is maintained in the dedicated Cashier Expense policy documentation.
