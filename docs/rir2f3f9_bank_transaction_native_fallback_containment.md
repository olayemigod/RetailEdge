# RIR2F3F9 — Bank Transaction Native Fallback Containment

## Goal

Make RetailEdge Bank Matching & Reconciliation the everyday operational owner of imported bank-transaction review, matching, approval and reconciliation, while retaining ERPNext Bank Transaction forms only as an explicit advanced/native-Desk fallback.

## Context

F3F7 introduced reusable `native_fallback` filtering based on EdgeSuite native-Desk access. F3F8 applied that contract to Payment Orders.

At the F3F8 freeze, Money still exposes `Bank Transactions` as a direct ERPNext DocType route. The EdgeSuite Bank Matching workspace also links individual Bank Transaction records and suggested accounting documents directly into native Desk.

The Bank Matching workspace already provides the operational queues, filters, candidate discovery, review, approval and reconciliation flow. Its final reconciliation action delegates through `retailedge.banking_operations.match_and_reconcile`; ERPNext remains the accounting/reconciliation authority.

## Decision

1. Keep `Bank Transaction` as ERPNext accounting/banking truth.
2. Keep `Bank Matching` (`bank-matching-reconciliation`) as the RetailEdge everyday operational owner.
3. Mark the Money `Bank Transactions` navigation item as `mode = native_fallback` and restrict it to the existing finance-role set.
4. In the Bank Matching workspace, derive `can_use_native_desk` from the final RetailEdge business-hub context and fail closed when that access context cannot be loaded.
5. For EdgeSuite-only users:
   - render Bank Transaction narration as non-clickable information;
   - render suggested accounting-document identity as non-clickable information;
   - do not show `Open Bank Transaction` or `Open Accounting Document` review actions.
6. For users allowed native Desk, preserve those explicit inspection links.
7. Keep the RetailEdge Bank Transaction Match audit-record link available because it is a RetailEdge operational record, not an ERPNext accounting-form fallback.

## Safety

- Do not create or mutate Bank Transactions in this slice.
- Do not alter matching, approval or reconciliation semantics.
- Do not mutate submitted accounting documents.
- Do not add a parallel bank ledger or reconciliation engine.
- Do not change `Import Bank Statement` ownership in F3F9.
- Do not change Payment Entry, Journal Entry, Sales Invoice, Purchase Invoice or GL posting logic.
- Do not change branch-scope contracts.
- Do not introduce a CoreEdge dependency.

## Out of Scope

- EdgeSuite-native bank statement import UX.
- Subscription/Subscription Plan ownership.
- Replacing ERPNext Bank Transaction forms.
- Changing reconciliation approval thresholds or reviewer roles.
- Broader containment of every native DocType link elsewhere in RetailEdge.

## Freeze Requirement

Freeze only when Theme Compatibility, Linters, clean Frappe v16 CI/full RetailEdge tests and governed EdgeSuite UI Candidate Compatibility all pass on the same exact head. Do not add a freeze commit after the gates pass.
