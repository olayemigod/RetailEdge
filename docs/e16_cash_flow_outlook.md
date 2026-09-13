# E16 13-Week Cash Commitments

## Topology decision

RetailEdge R12 / PR #32 already owns **Forecasting & Planning**, including behaviour-based cash forecasting and a simplified monthly known-due schedule. E16 must not create a second forecasting engine.

This E16 slice is therefore deliberately narrower: it is a read-only **known cash commitments schedule**. Its incremental value is that ERPNext v16 Accounts Receivable / Accounts Payable allocation splits current outstanding by native Payment Schedule terms before the amounts are placed into weekly buckets. R12's current helper groups invoice-level outstanding by invoice due month and does not perform this payment-term split.

When the intelligence stack is reconciled with the current transactional/E16 line, R12 must consume this payment-term commitment schedule (or the shared helper extracted from it) and its simplified `_cash_commitment_schedule` must be removed. The two commitment calculators must not remain in parallel.

## Scope

13-Week Cash Commitments is a read-only schedule of current submitted Sales Invoice receivables and Purchase Invoice payables.

- Due or overdue amounts are grouped into **Due now**.
- Future amounts are grouped into 13 weekly buckets.
- Invoice outstanding is split using ERPNext's native Accounts Receivable/Accounts Payable payment-term allocation.
- Company amounts use the native report's company-currency result.
- Branch filtering is applied by intersecting native AR/AP rows with the same permission-aware Sales Invoice and Purchase Invoice scopes already used by RetailEdge receivables/payables reporting.
- The page is available only to accounting/manager/auditor roles and still requires native read permission for both Sales Invoice and Purchase Invoice.

## What this is not

This is **not** a cash forecast, scenario planner, or projected bank balance. R12 Forecasting & Planning remains the owner of forecasting behaviour, plans, scenarios, forecast-vs-actual and planning intelligence.

The commitments view does not infer uncommitted future transactions and does not assume that an invoice will actually be collected or paid on its due date.

Excluded from this slice:

- opening cash/bank balances;
- Journal Entry receivables/payables, because RetailEdge cannot safely attribute them to Branch using the current invoice branch contract;
- Sales Orders and Purchase Orders;
- recurring/manual scenario assumptions;
- probability-weighted collections;
- automatic accounting or document posting.

## Safety contract

ERPNext remains source of truth. 13-Week Cash Commitments performs no `insert`, `save`, `submit`, GL Entry, Stock Ledger Entry, Payment Entry, Sales Invoice, Purchase Invoice or Payment Ledger mutation. Governed export uses the shared RetailEdge reporting capability layer.

## Reconciliation contract with R12

At consolidated-stack reconciliation:

1. preserve R12 behaviour-based cash forecast and Planning Scenario functionality;
2. replace R12's invoice-level monthly `_cash_commitment_schedule` source with the E16 native payment-term commitment source;
3. aggregate the shared commitment source to months where the R12 UI needs monthly display;
4. retain the 13-week weekly detail page for treasury/working-capital visibility;
5. keep the R12 rule that known commitments are evidence only and are not automatically added to behavioural cash forecasts;
6. run exact-head tests after reconciliation and keep only one commitment-calculation implementation.
