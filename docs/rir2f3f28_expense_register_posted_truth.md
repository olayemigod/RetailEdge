# RIR2F3F28 — Expense Register Posted-Truth Reporting

## Goal

Keep the consolidated Expense Register financially truthful while still allowing owners and managers to inspect unposted Cashier Expense exposure when needed.

## Reporting Contract

Posted accounting expense remains the financial reporting truth.

For the consolidated Expense Register:

- posted accounting-source rows remain included by default;
- Cashier Expense rows are included in the default financial view only when their ledger status is **Posted** and they have a posting reference;
- draft, submitted, rejected, Pending Ledger, failed, or otherwise unposted Cashier Expenses are excluded by default;
- eligible users can explicitly enable **Include unposted Cashier Expenses** to inspect those operational rows.

The opt-in does not silently add unposted Cashier Expenses to the posted-expense headline. Summary cards keep:

- **Posted Expenses**;
- **Unposted Cashier Exposure**;

as separate values.

## Expense Review Boundary

Expense Review remains an operational review/control queue. It may show submitted, pending, rejected, or other non-final Cashier Expense states because those are the records requiring action.

The posted-only default applies to consolidated owner/manager financial reporting, not to the review workflow itself.

## Operational Calculations

This slice does not change Cashier Expense workflow or posting.

RetailEdge operational calculations may still include unposted Cashier Expenses where the relevant existing setting or control explicitly requires them, including:

- available shift cash protection;
- variance/readiness analysis;
- pending-posting exposure;
- review workload;
- other documented operational controls.

Those operational figures must remain identified as pending/unposted exposure and must not be represented as posted accounting expense.

## Accounting Safety

This slice is read-only.

It does not:

- post Cashier Expenses;
- create GL Entry;
- change Cashier Expense approval states;
- change posting references;
- mutate Purchase Invoice, Expense Claim, Journal Entry, Payment Entry or submitted accounting documents;
- broaden Company or Branch scope;
- change Expense Category mappings.

## Tests Required

- consolidated default sets unposted inclusion to false;
- default Cashier Expense query requires Posted ledger state and posting reference;
- explicit opt-in can expose unposted Cashier Expense rows;
- posted and unposted totals remain separate;
- UI exposes a clear opt-in filter;
- operational calculation policy remains explicitly unchanged.

## Freeze Rule

Freeze F3F28 only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on one exact SHA.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.
