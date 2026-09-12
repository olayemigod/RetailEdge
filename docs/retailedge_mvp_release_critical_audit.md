# RetailEdge MVP Release-Critical Audit

## Authority

- Product: RetailEdge
- Repository: `olayemigod/RetailEdge`
- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Audit baseline: `6a06153742610f38e48b3ffb683f497944999105`
- Date: 2026-09-12

## Goal

Move RetailEdge from prolonged hardening into a production-ready MVP. Only work that can materially block real SME operation, accounting/stock integrity, access isolation, installation/upgrade, or release acceptance remains release-critical.

Residual selector polish, secondary report refinement and cosmetic containment are deferred unless they expose a security, branch-isolation or unusable-core-workflow defect.

## Evidence already accepted

### Core workflows

RIR2G1 is code-complete and classifies the standard MVP journeys as complete or intentionally advanced-fallback:

- selling: quotation -> sales order -> delivery -> sales invoice;
- customer receipts and advances;
- purchasing: purchase order -> receipt -> purchase invoice;
- supplier payments;
- purchase returns / supplier debit notes;
- cash deposits and internal transfers;
- cashier expenses;
- business expenses;
- bank matching handoff;
- customer receivables;
- supplier payables.

ERPNext remains authoritative for GL, Payment Ledger, Stock Ledger, valuation, outstanding balances and submitted document lifecycle.

### Expense management

The EdgeSuite Business Expenses surface already provides:

- non-POS business expense capture;
- evidence attachment;
- draft editing;
- workflow actions and approval state;
- controlled accounting posting;
- safe reversal;
- consolidated Expense Register visibility.

Do not rebuild this flow for MVP.

### EdgeSuite-first containment

The final navigation composition and Business Hub client contain raw DocType/Report routes when Native Desk capability is disabled. Deliberate advanced ERPNext boundaries remain available only to authorised Native-Desk-capable users.

### Fresh-install validation

The governed CI creates a clean Frappe v16 site, installs Payments + ERPNext + EdgeSuite UI + RetailEdge, builds assets, migrates and runs the full RetailEdge test suite. Fresh installation is therefore continuously exercised.

### Recent G2G selector hardening

G2G21-G2G29 improved context-aware option scope across reporting and review pages. These improvements remain accepted, but further selector-by-selector expansion is paused for MVP prioritisation.

## Release-critical backlog

### RC1 — Business Hub MVP Home — BLOCKER

The current Business Hub is a valid shell and navigation host but its home body is not yet the approved MVP command centre.

Current home body contains:

- company/branch identity;
- welcome banner;
- five experience cards;
- Create picker.

The approved MVP outcome requires a finished Home covering:

- Today;
- Stock;
- Banking;
- Branch;
- actionable Attention;
- quick actions.

At-a-glance business information must include the most useful available signals for:

- sales;
- money received;
- expenses;
- cash/bank;
- receivables/payables;
- stock / low-stock / out-of-stock;
- unmatched bank items;
- branch performance;
- overdue invoices;
- supplier balances;
- cash variance / unresolved operating exceptions.

Actions should prioritise:

- Make Sale;
- Receive Payment;
- Pay Supplier;
- Record Expense;
- Receive / Record Purchase;
- Transfer Stock;
- Match Bank Transactions.

All cards and actions must respect Company, Branch, permissions and the existing Native Desk capability boundary.

### RC2 — EdgeSuite completion for standard stock operations — BLOCKER FOR EDGESUITE-ONLY PERSONAS

Business Hub standard Sales Invoice, Purchase Invoice and Cash/Bank Transfer flows can continue into EdgeSuite completion surfaces.

Guided Stock Transfer and Stock Adjustment currently end at saved ERPNext drafts. The MVP must prove that a normal RetailEdge user can complete the approved standard stock journey without being stranded at a native-only handoff.

Required approach:

- support safe standard completion in EdgeSuite where ERPNext can submit normally;
- preserve Frappe Workflow precedence;
- keep complex serial/batch, valuation and exceptional stock cases as deliberate advanced ERPNext boundaries;
- never bypass ERPNext stock validation or mutate submitted documents.

### RC3 — Consolidated browser/persona QA — BLOCKER

`docs/rir2e_consolidated_browser_persona_qa.md` remains NOT RUN.

The release gate must exercise the exact candidate using real browser journeys for at least:

- Cashier / front-line operator;
- Branch Manager;
- Accounts / finance user;
- Owner / System Manager.

The QA must cover cross-workflow operation, permissions, EdgeSuite-only containment, branch switching/scope, loading/error/empty states and mobile/responsive usability where relevant.

### RC4 — Upgrade / migration validation — BLOCKER

Fresh install is continuously proven by CI, but the release also needs an upgrade test from a representative earlier RetailEdge site/baseline.

Required:

- install or restore prior baseline;
- populate representative transactional/setup data;
- upgrade app code;
- run `bench migrate`;
- prove patches and `after_migrate` hooks are idempotent;
- confirm existing roles, branch assignments, accounting documents and operational data remain intact;
- run focused smoke/regression tests after migration.

### RC5 — Release hardening and MVP freeze — BLOCKER

After RC1-RC4:

- rerun all governed exact-head gates;
- complete install + upgrade evidence;
- close release-critical browser findings;
- version/tag the MVP candidate;
- produce concise installation/upgrade notes and known advanced-native boundaries;
- freeze the MVP exact head.

## Do not block MVP on

Unless a new defect is security/accounting/branch-scope critical, defer:

- additional page-by-page dependent selector refinement after G2G29;
- advanced analytics beyond essential management visibility;
- conversion of every ERPNext specialist screen into EdgeSuite;
- cosmetic-only native fallback containment already hidden from EdgeSuite-only users;
- secondary report convenience refinements;
- low-value UI polishing that does not block the target personas.

## Execution order

1. RC1 Business Hub MVP Home.
2. RC2 standard stock-operation completion continuity.
3. RC3 consolidated browser/persona QA and targeted fixes only.
4. RC4 upgrade/migration validation.
5. RC5 release hardening, version/tag and MVP freeze.

This order supersedes the residual RIR2G2 selector-by-selector march for MVP execution.
