# Pre-reporting 13-Week Cash Commitments read-scope contract

## Business goal

The 13-Week Cash Commitments context, options, schedule, summaries and export may expose ERPNext receivable/payable payment-term allocations only inside the current reader's authorised Company and operational Branch scope. Client defaults and filters remain selections, never authority.

## B4B15 scope

This slice replaces the report's residual legacy default-Branch convention with the B3 operational Branch authority and explicitly revalidates a selected Branch before report capability evaluation. It also freezes the existing safety composition in which native ERPNext Accounts Receivable/Payable schedule rows are returned only when their invoice names exist in the hardened Customer Receivables and Purchase Reporting populations. It does not change payment-term allocation, week bucketing, commitment calculations, capabilities, forecasting, dashboards, navigation or document behavior.

## Company and Branch contract

- Company remains mandatory and native Company, Sales Invoice and Purchase Invoice read permissions remain required.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- A valid authorised default Branch remains selected.
- A stale or unauthorised restricted default is removed; exactly one active allowed Branch is selected only when unambiguous.
- An unrestricted reader may retain a valid legacy default or use the established Company-wide blank-Branch behavior.
- An explicit unauthorised Branch is rejected before report capability evaluation or native schedule execution.
- An authorised explicit Branch is revalidated against Company→Branch setup.
- Existing report capability policy continues to require an explicit Branch for restricted cross-branch reporting; this slice does not alter that policy.

## Schedule composition and safety boundaries

- Branch options continue through the bounded, permission-aware operational query.
- Customer Receivables supplies the permitted Sales Invoice names and Purchase Reporting supplies the permitted Purchase Invoice names.
- Native ERPNext Accounts Receivable/Payable allocation remains the payment-term and outstanding-value authority.
- Native rows are retained only when voucher type, permitted invoice name and positive outstanding amount all match.
- The permitted-name population is resolved before native schedule rows are processed.
- Screen and export reuse one dataset authority.
- Due-now/thirteen-week buckets, beyond-horizon totals, cumulative net commitments, scan metadata and capability composition remain unchanged.
- No cash balance, journal entry, order, manual scenario or forecast is introduced.
- No Sales Invoice, Purchase Invoice, GL Entry, Payment Entry or other document is mutated.

## Manual QA checklist

1. Restricted reader with one Branch: the default resolves to that Branch and only its permitted receivable/payable invoices contribute.
2. Restricted reader with multiple Branches: a valid selected Branch works; blank or unauthorised cross-branch scope fails closed under the existing capability policy.
3. Restricted reader with zero active Branches: the report cannot reach native schedule output.
4. Stale default Branch: it is removed and replaced only by one unambiguous active assignment.
5. Unrestricted manager with blank Branch: existing Company-wide commitments remain available.
6. Confirm native schedule rows for invoice names outside the hardened Sales/Purchase populations are discarded.
7. Compare screen and export for identical Company/Branch filters; all fourteen buckets and summaries must reconcile.
8. Confirm due-now, weeks 1–13, beyond-horizon and cumulative totals remain calculation-equivalent.
9. Confirm the page remains labelled commitments—not forecasting—and no cash balance, journal entry, order or manual scenario appears.
10. Confirm no accounting or business document is mutated by context, screen or export reads.
