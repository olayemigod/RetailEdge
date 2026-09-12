# RetailEdge MVP RC2 — Standard Stock Completion Continuity

## Goal

Remove the EdgeSuite-only dead end after the existing guided Stock Transfer and Stock Adjustment flows save valid ERPNext drafts.

## Scope

RC2 owns only the standard guided stock shapes already created by RetailEdge:

- **Stock Transfer:** ERPNext Stock Entry / Material Transfer with one Source Warehouse, one Target Warehouse, positive quantities and no Serial/Batch-managed items.
- **Stock Adjustment:** ERPNext Stock Reconciliation with one Warehouse, quantity-only physical counts and no Serial/Batch-managed items.

The guided creators remain draft-only. Completion is a separate review step.

## Completion contract

1. Load the saved document with normal read permission.
2. Require draft status and reject amended/unsupported shapes.
3. Revalidate Company, Warehouse and operational Branch authority at completion time.
4. Fail closed for restricted users when Warehouse→Branch scope cannot be proven.
5. Revalidate standard item/quantity constraints and keep Serial/Batch cases in Advanced ERPNext.
6. Inspect Frappe Workflow:
   - active Workflow wins;
   - only server-returned workflow actions are offered;
   - RetailEdge never writes workflow state directly.
7. Without an active Workflow, require normal submit permission.
8. Require the reviewed `modified` timestamp so stale completion is rejected.
9. Delegate final posting to ERPNext `doc.submit()`.
10. RetailEdge never creates or edits Stock Ledger entries, valuation truth, or submitted documents directly.

## UI

Business Hub now opens a shared **Standard Stock Completion** dialog immediately after either guided stock draft is saved.

The dialog shows:
- document/company/posting date;
- source/target warehouse and Branch scope for transfers;
- warehouse/Branch for adjustments;
- bounded item preview;
- blockers;
- active Workflow and permitted actions;
- direct Submit only when server-authorised;
- Advanced ERPNext only when Native Desk capability is available.

## Out of scope / deliberate advanced boundary

- Serial No or Batch-managed items.
- Multi-warehouse adjustments.
- Multi-source or multi-target transfers.
- Amended stock documents.
- Specialist valuation corrections.
- Exceptional ERPNext stock cases that fall outside the simple guided contract.

## Safety

- ERPNext owns Stock Ledger and valuation.
- No `ignore_permissions`.
- No manual `frappe.db.commit()`.
- No direct docstatus/workflow-state mutation.
- Submitted/cancelled stock documents are never mutated by the completion service.
