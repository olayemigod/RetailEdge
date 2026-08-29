# E16 Competitive Gap Audit — ERPNext-first baseline

This audit is the implementation filter after the E15 multi-app coexistence checkpoint.

## Rules

1. ERPNext remains the source of truth for accounting, stock, selling, buying, projects and payment documents.
2. Do not rebuild native ERPNext capabilities. Add guided orchestration, controls, collaboration and reporting where the native experience has a real usability or market gap.
3. EdgeSuite UI remains the shared frontend runtime.
4. The product must remain safe alongside other Frappe/ERPNext product apps.
5. E16 remains stacked on the exact green E15 checkpoint `1f01b27d02b322f49ecaaecf1103a4b7188d6fed`; continue the existing E16 branch/PR rather than creating divergent implementation lines.

## Native ERPNext capabilities that are not gaps

- Payment Terms / Payment Terms Template already cover deposits, instalments, credit periods and milestone schedules.
- Payment Request already provides invoice/order payment requests and gateway links.
- Subscription and Auto Repeat already cover recurring/retainer billing patterns.
- Dunning already provides formal overdue collection notices, optional interest/fees and linked payment handling.
- ERPNext Customer Portal already exposes customer/order information and Project portal access can expose tasks/timesheets.
- ERPNext Supplier portal already exposes Request for Quotation, Supplier Quotation, Purchase Order and Purchase Invoice with Supplier ownership checks derived from Portal User links.

The product should expose or orchestrate these safely rather than create parallel ledgers or duplicate recurring-billing, buying or payment documents.

## Priority A — Customer collaboration and self-service — IMPLEMENTED / GREEN

The EdgeSuite customer portal now extends native ERPNext documents without mutating submitted accounting documents:
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

Customer-facing project collaboration is available through native Project progress plus explicitly published Project Updates. Internal Project/Task/Timesheet/Expense Claim and project-linked sales/purchase documents remain ERPNext authority. Further Project collaboration should be added only where a confirmed UX gap remains.

## Priority C — Document capture assistance — IMPLEMENTED / VALIDATION ACTIVE

Supplier document extraction assistance now extends the governed intake queue without making extracted data authoritative:
- internal Purchase/Accounts users can record structured extracted document number/date, currency, subtotal, tax, total and document-visible Purchase Order reference;
- Supplier, Company, authoritative Purchase Order and the private source File are copied only from the already-authorized Supplier Document Intake record;
- extraction evidence is immutable after creation;
- Accepted/Rejected extraction decisions are separate immutable review records rather than edits to extraction evidence;
- a reviewed extraction cannot be re-reviewed; corrections require a new extraction record, preserving both evidence and decision history;
- provider confidence and raw provider payload are supported by the audit model, but the provider recording boundary is deliberately server-only and no OCR/vision vendor is hard-wired;
- Supplier Portal users receive no generic create/write permission on extraction or extraction-review DocTypes;
- neither manual nor future provider extraction creates or mutates Purchase Invoice, Purchase Order, Payment Entry, GL Entry or Stock Ledger Entry;
- extracted suggestions remain advisory until an internal human uses the appropriate native ERPNext buying workflow.

Promote this slice to GREEN only after exact-head Theme, Linters, standalone CI/full tests and EdgeSuite candidate compatibility pass.

## Current execution order

1. Preserve Priority-A checkpoint `273d795d4acd66b7478f8968a5a74ef40ff50681`.
2. Preserve Supplier Collaboration checkpoint `3a91fd6f0e93c34e8fe04dd72867db480e3becef`.
3. Preserve Supplier Document Intake checkpoint `9772d544feb9816ae5bd73d87b19117c4b99351a`.
4. Validate Supplier Document Extraction Assistance at exact head on the existing `agent/competitive-gap-nextgen-20260829` / PR #53 line.
5. After the extraction checkpoint is green, reassess the remaining competitive gaps before adding another E16 feature slice.
6. Keep manual QA deferred until implementation is complete and the cumulative E16 line is reconciled into the single consolidated QA branch.
