# E16 Competitive Gap Audit — ERPNext-first baseline

This audit is the implementation filter after the E15 multi-app coexistence checkpoint.

## Rules

1. ERPNext remains the source of truth for accounting, stock, selling, buying, projects and payment documents.
2. Do not rebuild native ERPNext capabilities. Add guided orchestration, controls, collaboration and reporting only where the native experience has a real usability or market gap.
3. EdgeSuite UI remains the shared frontend runtime. New operational pages, dialogs, filters, review queues and workflow surfaces must use the governed EdgeSuite runtime/shells/components rather than introducing a parallel frontend system.
4. The product must remain safe alongside other Frappe/ERPNext product apps.
5. E16 remains stacked on the exact green E15 checkpoint `1f01b27d02b322f49ecaaecf1103a4b7188d6fed`; continue the existing E16 branch/PR rather than creating divergent implementation lines.
6. Treat previously implemented RetailEdge programme capabilities as existing even where they remain on historical or QA reconciliation stacks. Reconcile them; do not reimplement them in E16.
7. Manual QA remains deferred until implementation is complete and the cumulative source line is reconciled into the single consolidated QA branch.

## Existing programme capabilities that are not E16 gaps

The competitive-gap audit must not duplicate already implemented RetailEdge programme work, including:

- Advanced Payment Management / advance receipt and invoice allocation work from the existing payments programme line;
- Project Operations / project funds, project receipts, project expenses and ERPNext Project-linked operational work from the existing project programme line;
- R8–R12 intelligence capabilities, including forecasting/planning, scenarios and other historical intelligence work carried by the consolidated QA stack;
- existing Banking & Reconciliation, reporting, branch operations, Professional Selling and guided-entry foundations.

Where E16 discovers a better source layer for one of these capabilities, document a reconciliation contract rather than leaving two implementations in parallel.

## Native ERPNext capabilities that are not gaps

- Payment Terms / Payment Terms Template already cover deposits, instalments, credit periods and milestone schedules.
- Payment Request already provides invoice/order payment requests and gateway links.
- Subscription and Auto Repeat already cover recurring/retainer billing patterns.
- Dunning already provides formal overdue collection notices, optional interest/fees and linked payment handling.
- ERPNext Customer Portal already exposes customer/order information and Project portal access can expose tasks/timesheets.
- ERPNext Supplier portal already exposes Request for Quotation, Supplier Quotation, Purchase Order and Purchase Invoice with Supplier ownership checks derived from Portal User links.

The product should expose or orchestrate these safely rather than create parallel ledgers or duplicate recurring-billing, buying or payment documents.

## Priority A — Customer collaboration and self-service — IMPLEMENTED / GREEN

The EdgeSuite customer portal extends native ERPNext documents without mutating submitted accounting documents:

- quotation accept/decline and transaction-scoped collaboration are append-only;
- invoice payment initiation uses native ERPNext Payment Request;
- outstanding, overdue, received-payment, available-advance and receivable statement context remain native accounting read models;
- project progress and only explicitly customer-published Project Updates are exposed;
- customer/company/document identity is server-derived and revalidated;
- PDF access uses ERPNext website permission and server-controlled Print Format selection;
- no direct Payment Entry, GL Entry or Stock Ledger Entry writes are introduced by portal self-service.

Validated checkpoint: `273d795d4acd66b7478f8968a5a74ef40ff50681`

- RetailEdge Theme Compatibility #105: PASS
- Linters #1800: PASS
- CI #1818, including full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #56: PASS

## Priority A — Receivables automation workspace — IMPLEMENTED / GREEN

The collections workspace orchestrates ERPNext Accounts Receivable, Payment Terms, Payment Request and Dunning with overdue prioritisation, governed handoffs, Action Follow Up scheduling, and branch/company/permission-aware queues. Action Follow Up remains operational metadata, not a shadow receivables or promise-to-pay ledger.

Validated with the same Priority-A checkpoint `273d795d4acd66b7478f8968a5a74ef40ff50681`.

## Priority B — Supplier collaboration — IMPLEMENTED / GREEN

ERPNext v16 remains authority for Request for Quotation, Supplier Quotation, Purchase Order and Purchase Invoice portal pages. RetailEdge adds only the collaboration and financial experience gaps:

- unified product-neutral supplier workspace over native ERPNext supplier routes;
- Supplier identity derived from Portal User links;
- append-only Purchase Order acknowledgement and messages with native website-permission checks and no Purchase Order mutation;
- read-only Purchase Invoice outstanding/overdue context;
- read-only submitted outgoing Payment Entry context;
- bounded supplier account statements from Payable Payment Ledger Entry;
- additive portal menu installation.

Validated checkpoint: `3a91fd6f0e93c34e8fe04dd72867db480e3becef`

- RetailEdge Theme Compatibility #108: PASS
- Linters #1806: PASS
- CI #1823, including clean Frappe v16 install/migration/assets and full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #61: PASS

## Priority B — Supplier document intake — IMPLEMENTED / GREEN

The Supplier intake slice provides a human-review document queue without creating any native buying transaction:

- `/supplier_documents` is a Supplier-role portal page installed additively;
- browser supplies only Purchase Order identity, document category, notes and file; Supplier and Company are derived on the server;
- the referenced Purchase Order must be submitted, supplier-owned and pass ERPNext native website permission;
- upload transport reuses Frappe's native POST `upload_file` boundary and then applies a stricter document MIME allowlist;
- each file is private and attached to a namespaced Supplier Document Intake record;
- Supplier Portal users have no generic create/write permission on the intake DocType;
- source identity is immutable after submission; internal Purchase/Accounts reviewers can change only review status/notes;
- Accepted/Rejected decisions are final in the intake audit trail;
- no Purchase Invoice, Purchase Order, Payment Entry, GL Entry or Stock Ledger Entry is created or mutated by intake.

Validated checkpoint: `9772d544feb9816ae5bd73d87b19117c4b99351a`

- RetailEdge Theme Compatibility #109: PASS
- Linters #1808: PASS
- CI #1826, including clean Frappe v16 install/migration/assets and full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #64: PASS

## Priority B — Project collaboration — PARTIALLY IMPLEMENTED / GREEN

Customer-facing project collaboration is available through native Project progress plus explicitly published Project Updates. Internal Project/Task/Timesheet/Expense Claim and project-linked sales/purchase documents remain ERPNext authority. Deeper project operations/project-funds work belongs to the existing Project Operations programme line and must be reconciled rather than rebuilt here.

## Priority C — Supplier document extraction assistance — IMPLEMENTED / GREEN

Supplier document extraction assistance extends the governed intake queue without making extracted data authoritative:

- internal Purchase/Accounts users can record structured extracted document number/date, currency, subtotal, tax, total and document-visible Purchase Order reference;
- Supplier, Company, authoritative Purchase Order and the private source File are copied only from the already-authorized Supplier Document Intake record;
- extraction evidence is immutable after creation;
- Accepted/Rejected extraction decisions are separate immutable review records rather than edits to extraction evidence;
- a reviewed extraction cannot be re-reviewed; corrections require a new extraction record, preserving evidence and decision history;
- provider confidence and raw provider payload are supported by the audit model, but the provider recording boundary is deliberately server-only and no OCR/vision vendor is hard-wired;
- Supplier Portal users receive no generic create/write permission on extraction or extraction-review DocTypes;
- neither manual nor future provider extraction creates or mutates Purchase Invoice, Purchase Order, Payment Entry, GL Entry or Stock Ledger Entry;
- extracted suggestions remain advisory until an internal human uses the appropriate native ERPNext buying workflow.

Validated checkpoint: `81aef915b993c1e69d430e9c8c5e2968542a4af2`

- RetailEdge Theme Compatibility #111: PASS
- Linters #1812: PASS
- CI #1830: PASS
- EdgeSuite UI Candidate Compatibility #68: PASS

## Priority C — 13-Week Cash Commitments — IMPLEMENTED / GREEN

RetailEdge now exposes a read-only known-due commitments layer over ERPNext v16 Accounts Receivable and Accounts Payable allocation:

- current submitted Sales Invoice receivables and Purchase Invoice payables are allocated using ERPNext native AR/AP logic;
- `based_on_payment_terms=1` splits current outstanding by native Payment Schedule terms;
- overdue/due balances are grouped into Due now and future balances into 13 weekly buckets;
- branch scope intersects native AR/AP output with RetailEdge permission-aware invoice scopes;
- amounts remain in company currency from the native report;
- no accounting, invoice, payment or stock document is mutated.

This is deliberately **not** a second forecasting engine. R12 / PR #32 remains the owner of behavioural forecasting, scenarios and forecast-vs-actual. At reconciliation, R12's simplified invoice-level commitment calculator must be replaced by this payment-term-aware commitment source so only one known-commitment calculator remains.

Validated checkpoint: `d52262d9b4110cc7eef5896e4574093b2c0d9bb6`

- RetailEdge Theme Compatibility #113: PASS
- Linters #1816: PASS
- CI #1834: PASS
- EdgeSuite UI Candidate Compatibility #71: PASS

## Priority C — Supplier document → draft Purchase Invoice handoff — IMPLEMENTED / GREEN

The buying handoff extends the supplier document review flow without making extracted values authoritative.

The workflow is intentionally staged:

1. Supplier submits a private Supplier Invoice against an authoritative submitted ERPNext Purchase Order.
2. Internal Purchase/Accounts staff review the source document in the EdgeSuite `Supplier Document Review` workspace.
3. Manual or future provider-neutral extraction is recorded as immutable advisory evidence.
4. Extraction is explicitly accepted/rejected.
5. The source document is explicitly accepted/rejected.
6. Only after both accepted states does an internal user explicitly prepare an ERPNext **draft Purchase Invoice**.

Safety and ERPNext authority:

- Supplier, Company, Purchase Order and private source File are server-derived and revalidated;
- the Purchase Invoice uses ERPNext's native Purchase Order → Purchase Invoice mapper;
- mapped PO items, remaining quantities, rates, taxes and Purchase Order links remain authoritative;
- extracted subtotal, tax and total are never written into the Purchase Invoice;
- accepted supplier document number/date may populate the draft supplier bill reference/date;
- an extracted currency mismatch fails closed against the ERPNext-mapped draft;
- the action inserts only a draft and never submits it;
- no Payment Entry, GL Entry or Stock Ledger Entry is created;
- one extraction can create only one immutable handoff audit record and repeat requests are idempotent;
- if a handed-off draft is deliberately deleted, the immutable handoff is retained and a new extraction is required before another handoff.

EdgeSuite frontend contract:

- `supplier-document-review` is an internal role-aware standard Page;
- it requires `window.EdgeSuiteUI` and mounts through `createEdgeApp`;
- it uses `EdgeAppShell`, `EdgeDashboardShell`, `EdgeDashboardGrid`, `EdgeDashboardSection` and `EdgeLinkField`;
- controls use the shared EdgeSuite field/button contract;
- no legacy `window.EdgeUI`, `frappe.ui.Dialog` or `frappe.prompt` is used by this workflow;
- Company → Branch and Supplier filtering is permission-aware and backend validated;
- the shared `Review & Approvals` navigation exposes the page only to Purchase/Accounts/System Manager roles.

Validated checkpoint: `40b8f1fc3f0293ae89df91e6ea157f40894c7d93`

- RetailEdge Theme Compatibility #119: PASS
- Linters #1828: PASS
- CI #1846, including clean Frappe v16 install, asset build and full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #84: PASS

## Priority C — Mixed Customer Settlement — IMPLEMENTED / GREEN

Mixed Customer Settlement extends the existing Advanced Payment Management programme rather than creating another payment or receivables ledger.

The EdgeSuite `Payment Management` workspace now provides an invoice-centred settlement flow:

- a submitted Sales Invoice is loaded with its current authoritative ERPNext outstanding amount;
- eligible submitted customer Payment Entries with positive unapplied amounts are shown from the existing advance read model;
- users may select and apply several eligible advances in one server request;
- the server bounds a mixed settlement to 20 advances, rejects duplicate Payment Entries, and revalidates every allocation through the existing single-advance primitive before delegating to ERPNext Payment Reconciliation;
- no manual database commit is introduced, so the Frappe request transaction remains the batch boundary rather than the browser issuing independent accounting writes;
- after reconciliation the workspace reloads the current ERPNext Sales Invoice outstanding amount;
- users may optionally create a standard ERPNext **draft Payment Entry** allocated to the same invoice for additional money received;
- Company, Customer, Branch and Sales Invoice allocation for the draft receipt are derived from the authoritative Sales Invoice on the server; browser input is limited to receipt details such as amount, date, mode, reference and remarks;
- the draft Payment Entry is never auto-submitted and the UI explicitly states that it does not reduce Sales Invoice outstanding until standard ERPNext submission;
- the submitted Sales Invoice `Payments` action now routes into the EdgeSuite `payment-management` settlement experience rather than opening a parallel Frappe advance-allocation dialog;
- multi-currency invoices, multi-currency advances and separate-party-advance-account cases continue to fall back to ERPNext's full Payment Reconciliation / Payment Entry workflows;
- no customer wallet, settlement ledger, direct Sales Invoice outstanding mutation, auto-submit, direct GL Entry or Stock Ledger Entry write is introduced.

Validated checkpoint: `5122464e21f9cdfceb52855e54302b11be074172`

- RetailEdge Theme Compatibility #126: PASS
- Linters #1842, including pre-commit, Semgrep and vulnerable dependency audit: PASS
- CI #1860, including clean Frappe v16 install, asset build, EdgeSuite asset contract and full RetailEdge tests: PASS
- EdgeSuite UI Candidate Compatibility #98, including clean build/migrate and full RetailEdge tests: PASS

## Current execution order

1. Preserve Priority-A checkpoint `273d795d4acd66b7478f8968a5a74ef40ff50681`.
2. Preserve Supplier Collaboration checkpoint `3a91fd6f0e93c34e8fe04dd72867db480e3becef`.
3. Preserve Supplier Document Intake checkpoint `9772d544feb9816ae5bd73d87b19117c4b99351a`.
4. Preserve Supplier Document Extraction checkpoint `81aef915b993c1e69d430e9c8c5e2968542a4af2`.
5. Preserve 13-Week Cash Commitments checkpoint `d52262d9b4110cc7eef5896e4574093b2c0d9bb6` and its R12 reconciliation contract.
6. Preserve Supplier Document → draft Purchase Invoice checkpoint `40b8f1fc3f0293ae89df91e6ea157f40894c7d93`.
7. Preserve Mixed Customer Settlement checkpoint `5122464e21f9cdfceb52855e54302b11be074172`.
8. Continue the fresh competitive-gap audit against the consolidated capability inventory before selecting another genuinely incremental E16 feature slice.
9. Do not create a divergent E16 PR/branch.
10. Keep manual QA deferred until implementation is complete and the cumulative source line is reconciled into the single consolidated QA branch.
