# RC3 — POS Till Cash Custody Spend Guard (11 November 2026)

## Incident class and invariant

A production shift reported negative expected cash despite all cashier expenses originating from RetailEdge. The shift-closing permission traceback is a **separate** POSNext draft-invoice cleanup problem; it does not explain why till expenses exceeded the final expected cash.

**Invariant:** A new RetailEdge POS Till expense must not commit unless the cashier's current shift has verified, nonnegative available till cash sufficient for the expense. Available cash = opening cash + attributable collected cash - active reserved/disbursed till expenses - submitted shift cash deposits. Card, bank or unrelated Cash-type payment methods are never a substitute for the POS Profile's selected till cash mode.

## Reconciled implementation (RetailEdge PR #250)

- Identify the exact POS Profile cash mode for both opening balance and Sales Invoice/Payment Entry tender. Do not treat every ledger typed `Cash` as the POS till.
- Deduct change given to customers from cash tender before recognising available funds.
- Count incoming Payment Entries only when explicitly linked to the exact POS opening shift, `payment_type=Receive`, and paid into that till's payment method/account. Company, Branch and time window alone are insufficient proof of till receipt.
- Never treat an incomplete invoice scan or failed expense/receipt query as zero liability. Mark unresolved cash sales unverified and refuse the new till expense with a business-readable error.
- Serialize new expenses and submitted deposits on the `POS Opening Shift` row. Read previous cash expenses and submitted deposits with current `FOR UPDATE` queries after this lock so a repeatable-read transaction cannot authorise concurrent overspending using an old read view.
- Keep submitted expense review/ledger transitions functional without changing their saved historical monetary snapshot. Other cash sources are not charged to the POS Till.
- Require an opening shift for a POS Till expense even when a merchant allows a non-till expense without an open shift.

## Remaining acceptance gates

1. CI, lint/format, v16 upgrade compatibility, and POSNext extension integration on the **same exact candidate**.
2. Cashier/manager positive and negative permission and Company/Branch/shift scope cases.
3. Simultaneous cash expenses, expense versus cash deposit, and repeated save/submit: only available funds can be consumed once. Check database transactions, not only the frontend button state.
4. Opening cash, strict named cash mode, cash and non-cash invoice payments, partial credit, customer change, shift-tagged customer receipts and unrelated Company/Branch receipts; closing preview must tie to the same attributable cash.
5. Zero sales must be a verified zero, and an incomplete query must fail closed; no external Payment Entry may inflate cash custody.
6. Submitted/approved/rejected/posted expense review after a shift closes must not re-run or overwrite historic spend-time cash validation.
7. Browser and mobile presentation through POSNext Extension PR #26; no duplicate expense route and no duplicate accounting entry.
8. Read-only historical shift forensic review, including saved before/after snapshots, first divergence, status/source/shift attribution and cash receipt cross-check. No automatic backfill or historical ledger mutation.
9. Neotex or any other hosted production deployment only after explicit site QA acceptance. Do not close a previously failed shift until its saved sales, expenses, deposits, credit and counted cash are reconciled.

## Boundaries

This is a forward-only cashier-expense safety correction. It does **not** reinterpret historic cash paid, recast accounting entries, delete saved Sales Invoices, grant Delete permissions, reconcile unexplained physical cash, or silently close an open production shift. POSNext's draft-invoice deletion permission failure requires an independently governed close-path correction.
