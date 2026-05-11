# RetailEdge Cashier Expense Structure Reset

RetailEdge Cashier Expense was recreated as a clean structural foundation after the earlier implementation became difficult to save, list, and maintain safely.

## What This Phase Includes

- A normal `RetailEdge Expense Category` DocType
- A normal `RetailEdge Cashier Expense` DocType
- Stable list-view configuration
- Workspace links for both DocTypes
- Basic structure tests for create/save/list behavior

## What This Phase Does Not Include

- autofill logic
- approval workflow
- posting logic
- Journal Entry creation
- Payment Entry creation
- role-specific workflow rules

## Product Direction

Expense Category exists so cashiers can choose a friendly category instead of selecting an accounting expense account directly.

Later phases will add:

- cashier autofill behavior
- POS shift linking logic
- approval and review flow
- optional accounting posting
