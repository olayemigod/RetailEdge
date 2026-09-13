# E16 C6A — Purchase Cycle Verification Contract

## Goal

Add practical purchase-cycle exception visibility to the existing EdgeSuite Purchase Register without creating a parallel three-way-match ledger, purchase approval engine, accounting gate, or posting workflow.

RetailEdge should help Purchase and Accounts users see whether submitted supplier invoices are connected to the native ERPNext Purchase Order / Purchase Receipt cycle and whether obvious line-level rate or quantity conditions deserve review before payment or follow-up.

## Context

ERPNext v16 remains authoritative for Purchase Order, Purchase Receipt, Purchase Invoice, Buying Settings, stock and accounting.

Native ERPNext already supports important preventive controls, including:

- `po_required` — Purchase Order required for Purchase Invoice / Receipt;
- `pr_required` — Purchase Receipt required for Purchase Invoice;
- `maintain_same_rate` plus Warn / Stop behavior and override role;
- over-order / over-billing controls in the native purchase cycle;
- direct native Purchase Order / Purchase Receipt references on Purchase Invoice Item.

C6A must therefore be advisory visibility over ERPNext truth. It must not duplicate or weaken those controls.

R10 Inventory Intelligence remains owner of reorder intelligence and is not part of C6A.

## Scope

Extend the existing `Purchase Register` data and EdgeSuite surface with bounded, invoice-level purchase-cycle verification indicators derived from submitted ERPNext Purchase Invoices and their native item references.

For ordinary submitted purchase invoices, expose:

- Purchase Order link coverage;
- Purchase Receipt link coverage;
- count of line-level review flags;
- compact verification status;
- concise review reason(s) suitable for operational triage.

Expose current ERPNext Buying Settings as report metadata so users understand whether PO, receipt and same-rate controls are configured as mandatory, warning or optional behavior.

### Verification statuses

Use neutral operational wording rather than claiming a formal accounting approval state:

- `Linked` — every relevant invoice line is linked to both a Purchase Order item and Purchase Receipt item and no C6A advisory variance is detected;
- `PO Linked` — relevant lines are consistently linked to Purchase Order items but receipt links are absent; this is not automatically an error because ERPNext may allow direct PO billing;
- `Mixed Links` — only part of the invoice has consistent PO / receipt reference coverage;
- `Unlinked` — no relevant line has a native PO or receipt reference;
- `Review` — one or more bounded advisory rate / quantity conditions require inspection;
- `Return` — Purchase Invoice return / credit-note rows are not forced through ordinary purchase-cycle matching semantics in C6A.

`Linked`, `PO Linked`, `Mixed Links`, and `Unlinked` are descriptions of native link coverage, not approval outcomes.

## Advisory line checks

Only use source fields already stored on native ERPNext purchase-cycle documents.

### Purchase Order reference

When `Purchase Invoice Item.purchase_order` and `po_detail` are present, resolve the referenced `Purchase Order Item` permission-safely and compare only bounded source values needed for C6A.

### Purchase Receipt reference

When `Purchase Invoice Item.purchase_receipt` and `pr_detail` are present, resolve the referenced `Purchase Receipt Item` permission-safely.

### Rate review

Use company-currency net rates where available (`base_net_rate`) to avoid false currency comparisons.

Flag an advisory rate difference only when a native linked source line exists and the company-currency net rate differs beyond a small numeric tolerance.

This remains informational even when ERPNext Buying Settings allow rate changes. Native `maintain_same_rate` behavior remains authoritative.

### Quantity review

Do **not** require exact equality. Partial receipt and partial billing are valid ERPNext workflows.

Only flag the obvious bounded case where the current Purchase Invoice line stock quantity exceeds the directly linked Purchase Receipt item's accepted stock quantity beyond tolerance.

Do not attempt to rebuild ERPNext cumulative over-billing calculations across historical invoices.

### Missing-reference interpretation

A missing receipt reference is not automatically a C6A exception when ERPNext Buying Settings permit direct billing.

If `pr_required` is enabled, surface that policy context; submitted documents are still assumed to have passed ERPNext's native validation.

Do not infer that service / non-stock items require a receipt merely because a receipt reference is absent.

## Frontend

Reuse the existing EdgeSuite `Purchase Register` page and shared `PurchaseReportingReport.vue` component.

Do not introduce a new frontend runtime or Frappe dialog.

Add compact columns such as:

- `Verification`
- `PO Links`
- `Receipt Links`
- `Review Flags`

Keep Purchase Invoice / Supplier / return links clickable through existing behavior.

If useful, add a lightweight `Verification` filter with values such as `All`, `Linked`, `PO Linked`, `Mixed Links`, `Unlinked`, `Review`, and `Return`.

Display native Buying Settings policy context in the report metadata without exposing unnecessary technical internals.

## Backend

Prefer extending `retailedge/purchase_reporting.py` rather than creating a second purchase-reporting service.

Requirements:

- preserve existing Company / Branch / Supplier / date / item / warehouse filtering;
- preserve submitted Purchase Invoice as the report source;
- bounded child-row scans using existing purchase-report limits;
- permission-aware `frappe.get_list` / document access patterns;
- fail closed on excessive scope;
- no `ignore_permissions=True`;
- no direct SQL unless a reviewed need is proven;
- no writes or commits.

## Safety Rules

C6A MUST NOT:

- submit, cancel, amend or mutate Purchase Invoice, Purchase Order or Purchase Receipt;
- create Payment Entry, Payment Order, Journal Entry, Debit Note or Purchase Return;
- write GL Entry or Stock Ledger Entry;
- create a persistent match-status DocType;
- create a second approval workflow;
- block payment automatically;
- replace ERPNext Buying Settings validation;
- treat extracted supplier-document values as accounting authority;
- change R10 reorder / inventory intelligence behavior.

## Tests Required

Add focused unit / contract coverage for:

- fully linked PO + receipt lines;
- PO-only coverage without falsely calling it an error;
- mixed / unlinked coverage;
- rate difference using company-currency net rate;
- partial billing not falsely flagged solely because quantities are unequal;
- invoice quantity exceeding directly linked accepted receipt quantity is flagged;
- returns are classified separately;
- Buying Settings policy metadata is returned read-only;
- existing Branch / permission filtering remains intact;
- EdgeSuite Purchase Register exposes the new indicators without a parallel dialog/runtime;
- no accounting / stock writes, auto-submit or permission bypass patterns.

## Expected Deliverables

- bounded purchase-cycle verification logic in existing purchase reporting;
- EdgeSuite Purchase Register indicators / filter;
- focused tests;
- exact-head Theme, Linters, clean Frappe v16 CI and governed EdgeSuite compatibility validation;
- checkpoint documentation on PR #53.

## Out of Scope / Later

- payment blocking or approval gating;
- automated invoice correction;
- OCR/extracted-value matching;
- cumulative historical over-billing engine;
- formal vendor dispute workflow;
- R10 replenishment changes;
- purchase return / debit note / landed-cost wrappers already owned by ERPNext;
- manual QA before cumulative implementation reconciliation.
