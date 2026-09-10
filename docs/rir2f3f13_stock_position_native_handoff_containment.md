# RIR2 F3F13 — Stock Position Native Handoff Containment

## Goal

Keep Stock Position fully useful as an EdgeSuite read/report surface while preventing users without final Native Desk access from opening native ERPNext/Frappe Item or Material Request forms.

## Evidence

The current Stock Position component loads both:

- the permission-filtered RetailEdge Business Hub navigation context; and
- the replenishment handoff capability returned by `get_replenishment_handoff_context()`.

The replenishment backend already revalidates report access, company/branch/warehouse scope, Material Request create permission, item validity, reorder rules, and whether replenishment remains due. However, the client currently treats Material Request create permission as sufficient to open an unsaved native Material Request form and always makes Item codes clickable.

That permits an interface-level escape from EdgeSuite for users whose final shared access context has `can_use_native_desk = false`.

## Contract

For a user whose final EdgeSuite access context has `can_use_native_desk = false`:

- Stock Position remains readable and exportable according to existing permissions and branch/warehouse scope;
- Item codes are not presented as native-detail links;
- reorder-due signals remain visible but are not presented as native Material Request actions;
- no Item form, Material Request form, native DocType list, or native query report may be opened by the component;
- client capability defaults to fail closed before navigation context resolves.

For a user whose final EdgeSuite access context has `can_use_native_desk = true`:

- Item detail handoff remains available;
- the existing replenishment handoff remains available only when the server also reports Material Request create permission;
- existing server-side branch/warehouse/reorder/create-permission revalidation remains authoritative.

## Safety Rules

This slice must not change:

- Stock Position calculations or report scope;
- Branch Assignment precedence or restricted-zero fail-closed behavior;
- warehouse authorization;
- Item reorder rules or reorder quantity calculation;
- Material Request document semantics;
- Stock Entry behavior;
- Stock Ledger, valuation, General Ledger, posting, submission, or cancellation semantics;
- existing ERPNext/Frappe permission enforcement.

Frontend gating is interface exposure control only; it must not replace backend authorization.

## Out of Scope

- an EdgeSuite-native Material Request editor;
- a new replenishment engine;
- changing who is allowed to create Material Requests in ERPNext;
- redesigning Stock Position;
- unrelated native handoffs in Purchase Reporting, Customer Receivables, Professional Purchasing, or other pages.

## Required Evidence

- focused static contract test covering fail-closed access, click affordances, native route guards, and preservation of the server handoff;
- relevant Stock Position regression tests;
- exact-head RetailEdge Theme Compatibility;
- Linters / Semgrep / vulnerable dependency audit;
- clean Frappe v16 integration and RetailEdge suite;
- governed EdgeSuite UI candidate compatibility;
- authenticated Native Desk allowed/denied browser/persona QA before the slice is represented as fully frozen.

Until the browser/persona evidence exists, the maximum state is `CODE-FROZEN / QA-PENDING`.
