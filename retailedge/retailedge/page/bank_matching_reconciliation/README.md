# Bank Matching & Reconciliation

This EdgeSuite-facing RetailEdge page separates imported bank activity by canonical direction (`All`, `Inflow`, `Outflow`) and operational queue (`To Match`, `To Reconcile`, `Exceptions`, `Reconciled`).

The page must not treat a confirmed match as accounting completion. Reconciliation remains authoritative only when ERPNext Bank Transaction allocation/reconciliation state confirms completion.

Candidate categories include customer receipts, POSNext-backed sales payment events, deposit to bank, supplier payments, bank-funded expenses, transfers, refunds, charges and other valid accounting movements.
