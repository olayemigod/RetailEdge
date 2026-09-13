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
8. New implementation work is delivered in bounded checkpoints: audit/contract → one implementation slice → focused tests → exact-head validation → checkpoint documentation. Do not begin the next feature slice before the current checkpoint is green.

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
- ERPNext Purchase Order → Purchase Receipt mapping already owns remaining receivable quantities, PO item links, taxes, warehouses and receipt preparation.

The product should expose or orchestrate these safely rather than create parallel ledgers or duplicate recurring-billing, buying or payment documents.

## Priority A — Customer collaboration and self-service — IMPLEMENTED / GREEN

Validated checkpoint: `273d795d4acd66b7478f8968a5a74ef40ff50681`

- RetailEdge Theme Compatibility #105: PASS
- Linters #1800: PASS
- CI #1818: PASS
- EdgeSuite UI Candidate Compatibility #56: PASS

## Priority A — Receivables automation workspace — IMPLEMENTED / GREEN

Validated with Priority-A checkpoint `273d795d4acd66b7478f8968a5a74ef40ff50681`.

## Priority B — Supplier collaboration — IMPLEMENTED / GREEN

Validated checkpoint: `3a91fd6f0e93c34e8fe04dd72867db480e3becef`

- RetailEdge Theme Compatibility #108: PASS
- Linters #1806: PASS
- CI #1823: PASS
- EdgeSuite UI Candidate Compatibility #61: PASS

## Priority B — Supplier document intake — IMPLEMENTED / GREEN

Validated checkpoint: `9772d544feb9816ae5bd73d87b19117c4b99351a`

- RetailEdge Theme Compatibility #109: PASS
- Linters #1808: PASS
- CI #1826: PASS
- EdgeSuite UI Candidate Compatibility #64: PASS

## Priority B — Project collaboration — PARTIALLY IMPLEMENTED / GREEN

Customer-facing project collaboration is available through native Project progress plus explicitly published Project Updates. Deeper project operations/project-funds work belongs to the existing Project Operations programme line and must be reconciled rather than rebuilt here.

## Priority C — Supplier document extraction assistance — IMPLEMENTED / GREEN

Validated checkpoint: `81aef915b993c1e69d430e9c8c5e2968542a4af2`

- RetailEdge Theme Compatibility #111: PASS
- Linters #1812: PASS
- CI #1830: PASS
- EdgeSuite UI Candidate Compatibility #68: PASS

## Priority C — 13-Week Cash Commitments — IMPLEMENTED / GREEN

Validated checkpoint: `d52262d9b4110cc7eef5896e4574093b2c0d9bb6`

- RetailEdge Theme Compatibility #113: PASS
- Linters #1816: PASS
- CI #1834: PASS
- EdgeSuite UI Candidate Compatibility #71: PASS

R12 / PR #32 remains the forecasting owner and must consume this commitment source when stacks are reconciled.

## Priority C — Supplier document → draft Purchase Invoice handoff — IMPLEMENTED / GREEN

Validated checkpoint: `40b8f1fc3f0293ae89df91e6ea157f40894c7d93`

- RetailEdge Theme Compatibility #119: PASS
- Linters #1828: PASS
- CI #1846: PASS
- EdgeSuite UI Candidate Compatibility #84: PASS

## Priority C — Mixed Customer Settlement — IMPLEMENTED / GREEN

Validated checkpoint: `5122464e21f9cdfceb52855e54302b11be074172`

- RetailEdge Theme Compatibility #126: PASS
- Linters #1842: PASS
- CI #1860: PASS
- EdgeSuite UI Candidate Compatibility #98: PASS

## Priority C — Professional Purchasing C1: PO operations + PO → draft Purchase Receipt — IMPLEMENTED / GREEN

Professional Purchasing C1 closes the internal operational gap between existing native buying routes and supplier-facing collaboration without creating a second procurement system.

Delivered scope:

- standard EdgeSuite `professional-purchasing` page for permitted Purchase/Accounts/System Manager users;
- Company + optional Branch/Supplier filtering with backend permission and Branch validation;
- permission-aware Purchase Order queue showing status, transaction date, supplier, total, percent received and percent billed from ERPNext;
- sortable operational table while preserving the authoritative server dataset;
- native Purchase Order creation/list/form and Purchase Receipt routes remain available;
- submitted eligible Purchase Orders expose `Prepare Receipt`;
- receipt preparation delegates to ERPNext v16 `make_purchase_receipt` after server revalidation;
- mapped Purchase Receipt is inserted as **draft only** as the current user;
- mapped Company/Supplier and Branch access are revalidated;
- draft/cancelled/non-open, fully received, subcontracted, no-remaining-item and denied-Branch cases fail closed or fall back to the native ERPNext workflow;
- no Purchase Receipt submit, manual commit, direct PO progress mutation, Purchase Invoice creation or direct GL/SLE write;
- Professional Purchasing is promoted before native Purchase Orders without removing native Purchase Order/Purchase Receipt fallbacks.

Implementation checkpoint: `7fc24e993f908cdc28b72dc841f2771a21b570d3`

- RetailEdge Theme Compatibility #141: PASS
- Linters #1872: PASS
- CI #1890: PASS
- EdgeSuite UI Candidate Compatibility #128: PASS

Recovery-plan checkpoint: `d8d81994ab5152bf690eed75ae810bb3de294dc1`

- RetailEdge Theme Compatibility #142: PASS
- Linters #1873 and #1874: PASS
- CI #1891: PASS
- EdgeSuite UI Candidate Compatibility #129 and #130: PASS

The C1 recovery contract is `docs/e16_professional_purchasing_plan.md`.

## Current execution order

1. Preserve all existing green checkpoints above.
2. Preserve Professional Purchasing C1 implementation checkpoint `7fc24e993f908cdc28b72dc841f2771a21b570d3`.
3. Treat the current documentation-only PR head as the C1 closeout head; validate its exact Theme/Linters/CI/EdgeSuite gates before beginning C2.
4. Start **Professional Purchasing C2 as an audit/contract chunk only** after that closeout head is green.
5. Re-audit Material Request, Request for Quotation, Supplier Quotation, Supplier Collaboration and Project Operations before deciding whether any C2 implementation is genuinely incremental.
6. Inspect exact ERPNext v16 mapper/permission contracts immediately before defining C2.
7. Write the bounded C2 contract into `docs/e16_professional_purchasing_plan.md` before any C2 feature code.
8. Implement only the approved C2 slice; repeat focused tests, diff check, exact-head validation and checkpoint documentation before C3.
9. Do not create a divergent E16 PR/branch.
10. Keep manual QA deferred until implementation is complete and the cumulative source line is reconciled into the single consolidated QA branch.
