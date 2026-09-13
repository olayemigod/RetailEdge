# R9 — Business Control & Financial Intelligence

## Goal

Turn RetailEdge's existing sales, stock, expense, cash, action-centre, owner-dashboard and profitability foundations into a practical business-control layer for owners and managers without creating a parallel accounting system.

ERPNext remains the accounting and stock system of record. R9 should interpret, reconcile and surface control exceptions from ERPNext truth; it must not mutate submitted accounting documents or invent competing balances.

## Stack

- Predecessor: R8 — Owner & Profitability Intelligence
- Predecessor branch: `agent/owner-profitability-intelligence`
- R9 branch: `agent/business-control-financial-intelligence`
- R9 must remain directly stacked on R8 until R8 is promoted/rebased.
- Manual/browser QA for R9 must wait for predecessor QA/promotion, with reconciliation and exact-head CI before R9 QA begins.

## Initial Business Scope

### 1. Business Control Centre

Create an owner/manager control surface that prioritises exceptions requiring action rather than duplicating dashboards.

Candidate control families:

- cash and bank control;
- overdue receivables;
- overdue payables;
- expense/budget pressure;
- stock value and slow/non-moving exposure where reliable;
- margin leakage and missing recorded cost from R8;
- reconciliation exceptions;
- unusual or deteriorating business trends;
- unresolved Action Centre follow-ups.

Controls should carry severity, business impact, source, ageing, responsible context, drill-through and follow-up state where appropriate.

### 2. Financial Position Snapshot

Provide a simplified owner-facing financial position sourced from ERPNext ledgers/reports, including only values that can be reconciled safely.

Candidate measures:

- cash and bank balances;
- receivables outstanding;
- payables outstanding;
- accounting income/expense/net profit for the selected period;
- transactional sales-margin contribution from R8, clearly distinguished from accounting profit;
- stock value where ERPNext valuation data and permissions allow it;
- working-capital indicators derived from authoritative balances.

### 3. Cash-Flow & Liquidity Intelligence

Build operational liquidity views from ERPNext accounting/payment truth rather than invoice totals alone.

Candidate intelligence:

- current liquid cash/bank position;
- cash inflow/outflow trend;
- near-term expected customer collections;
- near-term supplier obligations;
- liquidity gap / coverage indicators;
- branch/company scope with explicit limits where accounting dimensions do not support safe branch attribution.

Do not label forecasts as accounting balances.

### 4. Receivables & Collections Control

Surface actionable customer debt controls using submitted Sales Invoice and Payment Entry allocation truth.

Candidate intelligence:

- overdue amount and ageing;
- high-risk customer exposure;
- invoices newly overdue;
- oldest receivables;
- collection trend;
- customer concentration;
- drill-through to native accounting documents in a new tab.

### 5. Payables & Supplier Control

Surface supplier obligations using submitted Purchase Invoice and Payment Entry allocation truth.

Candidate intelligence:

- overdue payables and ageing;
- upcoming obligations;
- supplier concentration;
- oldest unpaid invoices;
- unusual liability growth;
- drill-through to native accounting documents in a new tab.

### 6. Budget / Spend Governance

Extend the R5 expense-budget foundation into management controls without replacing ERPNext budgeting.

Candidate controls:

- budget consumed vs remaining;
- burn rate and projected overrun;
- unusually large expense movements;
- branch/company/category pressure;
- repeated unbudgeted spend;
- clear distinction between RetailEdge operational budget intelligence and ERPNext accounting truth.

### 7. Control Trends & Early Warning

Support bounded previous-period and trend comparisons for control metrics so RetailEdge can identify deterioration before it becomes a large exception.

Examples:

- receivables ageing worsening;
- payable pressure increasing;
- cash coverage weakening;
- expense burn accelerating;
- margin leakage increasing;
- stock exposure rising.

Trend logic must use comparable periods and must expose when comparison data is unavailable or incomplete.

## Product / Architecture Layer

R9 belongs in the RetailEdge product layer.

Reuse shared EdgeSuite UI/report/dashboard primitives and existing RetailEdge permission, branch/company, export/print, Action Centre and follow-up frameworks. Do not move RetailEdge-specific financial-control semantics into CoreEdge.

Cross-product primitives that later prove generic should be promoted separately rather than prematurely abstracted during R9.

## Accounting Safety Rules

- ERPNext General Ledger / accounting reports remain authoritative for accounting balances and profit.
- Submitted accounting documents must never be mutated for intelligence purposes.
- Do not create a second receivables/payables ledger.
- Do not infer paid status from unrelated invoices or payments.
- Payment allocations must respect ERPNext references and document status.
- Branch-level accounting claims must fail closed when branch is not represented by a valid ERPNext accounting dimension / Cost Center mapping.
- Stock valuation must use ERPNext valuation sources and existing RetailEdge cost-visibility policy.
- No `ignore_permissions` for user-facing data APIs.
- All scans must be bounded and permission-aware.

## Smart Filter Rules

- Company is the primary accounting scope.
- Branch must cascade from Company and clear when Company changes.
- Customer/Supplier/Account/Warehouse/Cost Center options must be permission-aware and context-filtered.
- Frontend filtering must be backed by server-side validation where correctness, accounting scope or tenant isolation is involved.
- Native ERPNext accounting/document links that remain exposed should open in a new tab with `noopener,noreferrer`.

## Initial Implementation Order

1. Audit current RetailEdge financial/control data sources and reusable R5/R8 services.
2. Define canonical control metrics and reconciliation rules against ERPNext reports/ledgers.
3. Implement Business Control Centre service contract and first control families.
4. Implement Financial Position Snapshot.
5. Implement receivables/payables control intelligence.
6. Implement liquidity/cash-flow intelligence.
7. Integrate budget/spend controls and R8 profitability exceptions.
8. Integrate Action Centre follow-up where it adds operational ownership without changing source-document truth.
9. Add shared export/print support and bounded all-filtered datasets.
10. Complete automated validation before manual/browser QA.

## Tests Required

### Unit

- metric calculations and severity rules;
- ageing buckets and due-date boundaries;
- payment-allocation handling;
- previous-period comparison;
- working-capital/liquidity formula handling;
- branch/company validation;
- permission/cost-visibility fail-closed behaviour.

### Integration

- ERPNext receivables/payables truth reconciliation;
- P&L/account balance reconciliation where surfaced;
- Payment Entry allocation scenarios;
- returns/credit notes and cancellations;
- branch/company restrictions;
- Action Centre/follow-up integration;
- export/print permission scopes.

### Migration

- clean Frappe v16 installation/migration;
- idempotent schema/patch changes;
- upgrade from the R8 predecessor state.

### Manual QA

Manual/browser QA starts only after predecessor QA/promotion is accepted and R9 has been reconciled to the promoted predecessor with fresh exact-head CI/Linter success.

## Out of Scope for Initial Slice

- mutating submitted accounting documents;
- replacing ERPNext Profit and Loss, General Ledger, Accounts Receivable, Accounts Payable or stock valuation engines;
- AI-generated financial advice presented as accounting fact;
- unrestricted forecasting or unbounded historical scans;
- premature CoreEdge abstraction;
- broad redesign of completed R5/R8 functionality.
