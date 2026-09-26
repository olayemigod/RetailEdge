# Cashier Expense Posting Policy + POS Closing Integration

## Goal

Keep RetailEdge Cashier Expense as the authoritative cashier-expense workflow while allowing each merchant to choose how accounting posting is controlled and ensuring real POS-till expenses are reflected in POS closing.

This phase deliberately does **not** adopt POSNext's native expense accounting workflow. One expense must have one operational record and one accounting posting.

## Merchant policy

RetailEdge Settings > Cashier Expenses now exposes:

- **Cashier Expense Posting Mode**
  - **Controlled Posting** — default and backward-compatible. Cashier submission records the till movement; a reviewer approves it into Pending Ledger; an authorised accounting/management user posts the Journal Entry.
  - **Direct Posting** — after submission RetailEdge attempts the same Journal Entry posting service immediately.
- **Enable Cashier Expense in POS** — enables the supported POS bridge.
- **Show Cashier Expense Action in POS** — advertises the action to a supported POS frontend integration.
- **Include Cashier Expenses in POS Closing** — adjusts expected POS cash for submitted/disbursed RetailEdge till expenses.

The legacy Require Approval Before Posting flag is retained for compatibility but is synchronized from the new posting-mode selector.

## Cash truth versus accounting truth

Cash and ledger state are separate:

- `cash_movement_status`: Not Disbursed / Disbursed / Returned / Reversed
- `ledger_status`: Not Applicable / Pending Ledger / Posted / Failed
- `expense_status`: operational review state

A submitted POS-till expense is marked **Disbursed** and reduces expected closing cash even if review/accounting is still pending. Rejection does not automatically mark cash Returned.

Draft Business Hub expenses retain the existing cash-availability reservation behavior, but POS closing counts only actual Disbursed till expenses.

## Accounting safety

Accounting posting creates one submitted ERPNext Journal Entry:

- debit: resolved Expense Account
- credit: resolved POS cash/payment account
- cost centre: resolved Cashier Expense cost centre
- branch attribution: applied when the Journal Entry has the RetailEdge branch field

The service is idempotent through the Cashier Expense posting reference and locks the source row before posting.

Direct Posting does not bypass ERPNext permissions. The user must still have the required Journal Entry permissions. If direct posting cannot complete, the Cashier Expense remains submitted/disbursed and is marked `ledger_status = Failed` with a user-safe posting message. This prevents an accounting permission problem from erasing a real till movement.

Posted Cashier Expenses cannot be cancelled while their accounting reference is active.

## POS capture bridge

Supported POS frontends can call:

- `retailedge.pos_cashier_expense.get_pos_cashier_expense_capabilities`
- `retailedge.pos_cashier_expense.create_pos_cashier_expense`
- `retailedge.pos_cashier_expense.get_pos_closing_cashier_expense_summary`

The create endpoint accepts only business inputs such as category, amount, description, date, receipt URL and `client_request_id`. Company, Branch, cashier, POS Profile, opening shift, payment account, expense account and cost centre are resolved and validated server-side.

`client_request_id` is unique and required so POS retry/offline replay cannot duplicate an expense.

## POSNext closing integration

RetailEdge does not modify the POSNext package.

An idempotent `POS Closing Shift.validate` hook:

1. reads the previous RetailEdge adjustment already stored on the draft closing shift;
2. restores that previous amount to obtain the POSNext baseline;
3. recalculates current submitted/disbursed RetailEdge POS-till expenses for the opening shift;
4. subtracts the current total once from the POS cash expected amount;
5. recalculates the cash-row difference;
6. stores Cashier Expense total/count/note on POS Closing Shift.

This makes repeated save/validate calls safe and allows new eligible expenses recorded before final closing submission to be included.

## POSNext screen action

The RetailEdge backend bridge is ready for a POSNext action/button. RetailEdge intentionally does not monkey-patch or copy the POSNext frontend. The currently inspected public POSNext develop branch does not expose a stable Cashier Expense extension hook, so the button should be connected through the ProcessEdge POSNext extension layer when that hook/version is available.

Until that frontend bridge is connected, RetailEdge Cashier Expenses are still included in POS closing when the integration setting is enabled.

Do not use POSNext native expense posting and RetailEdge Cashier Expense for the same till expense.

## Migration

The post-model-sync patch:

- maps legacy approval policy to Controlled/Direct when the new setting is blank;
- marks existing records with source and cash source;
- treats submitted historical Cashier Expenses as Disbursed;
- keeps draft historical expenses as Not Disbursed;
- marks cancelled historical expenses as Reversed.

POS Closing Shift custom fields are added idempotently after migrate.

## Manual QA

1. Migrate the site and confirm Cashier Expense Posting Mode defaults to Controlled Posting.
2. Enable Cashier Expense in POS and Include Cashier Expenses in POS Closing.
3. Open a POSNext shift and record/submit a RetailEdge Cashier Expense.
4. Confirm the expense has the correct Company, Branch, POS Profile, opening shift, cashier and category-derived accounts.
5. Create a POS Closing Shift and verify Cashier Expenses reduce only the cash expected amount.
6. Save the closing draft repeatedly and verify the expense is not deducted twice.
7. Record a second expense before closing submission and verify the expected amount refreshes by only the incremental amount.
8. Controlled mode: approve the expense, then Post to Accounts; verify one submitted Journal Entry and a Posted ledger state.
9. Direct mode with accounting-capable user: submit and verify immediate Journal Entry posting.
10. Direct mode without Journal Entry permission: verify the till expense remains recorded, closing still includes it, and ledger status becomes Failed with a clear message.
11. Retry a POS create call using the same client request ID and verify the original Cashier Expense is returned.
12. Verify a user cannot spoof Company, Branch, POS Profile or opening shift through the POS API.
13. Verify rejected-but-disbursed expenses remain in closing cash.
14. Verify Returned/Reversed cash no longer reduces shift cash.
15. Verify a Posted Cashier Expense cannot be cancelled while its Journal Entry is active.
