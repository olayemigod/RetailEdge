# E16 Cash Flow Outlook

## Competitive gap

Current SME accounting products increasingly surface forward-looking cash-flow planning. ERPNext v16 already contains the authoritative ingredients for a safe first outlook: Accounts Receivable and Accounts Payable are based on Payment Ledger Entry, allocate invoice outstanding across native Payment Schedule rows, and expose due dates. RetailEdge should orchestrate those native balances rather than create a parallel forecast ledger.

## Scope

Cash Flow Outlook is a read-only 13-week schedule of current submitted Sales Invoice receivables and Purchase Invoice payables.

- Due or overdue amounts are grouped into **Due now**.
- Future amounts are grouped into 13 weekly buckets.
- Invoice outstanding is split using ERPNext's native Accounts Receivable/Accounts Payable payment-term allocation.
- Company amounts use the native report's company-currency result.
- Branch filtering is applied by intersecting native AR/AP rows with the same permission-aware Sales Invoice and Purchase Invoice scopes already used by RetailEdge receivables/payables reporting.
- The page is available only to accounting/manager/auditor roles and still requires native read permission for both Sales Invoice and Purchase Invoice.

## Explicit exclusions

The first outlook does **not** claim to be a projected bank balance. It does not create a cash-planning ledger and does not infer uncommitted future transactions.

Excluded from the first slice:

- opening cash/bank balances;
- Journal Entry receivables/payables, because RetailEdge cannot safely attribute them to Branch using the current invoice branch contract;
- Sales Orders and Purchase Orders;
- recurring/manual scenario assumptions;
- probability-weighted collections;
- automatic accounting or document posting.

These exclusions are returned as report metadata and are visible in the EdgeSuite page so users cannot mistake scheduled invoice movement for forecast cash on hand.

## Safety contract

ERPNext remains source of truth. Cash Flow Outlook performs no `insert`, `save`, `submit`, GL Entry, Stock Ledger Entry, Payment Entry, Sales Invoice, Purchase Invoice or Payment Ledger mutation. Governed export uses the shared RetailEdge reporting capability layer.
