# RetailEdge Business Hub Pre-Merge Hardening

Status: active  
Branch: `qa/retailedge-visual-identity`  
PR: #56  
Release target: RetailEdge 1.0

## Goal

Strengthen Business Hub and its guided operational flows before the second MVP audit is frozen. Keep ERPNext accounting, stock and permission truth authoritative while making RetailEdge EdgeSuite-first for ordinary users.

## Phase 1 — Hub foundation and runtime stability

Status: implemented; automated validation pending.

Scope:
- Keep Business Hub mounted and recover cleanly on browser Back/Forward navigation.
- Replace the static “Five connected experiences” cards with functional command-centre sections:
  - Navigate = persistent EdgeSuite shell/sidebar.
  - Act = quick actions.
  - Operate = operational stock/banking/branch/cash signals.
  - Understand = date-filtered business KPIs.
  - Respond = attention and exception queue.
- Add bounded Business Hub period presets.
- Reduce non-essential rider copy.
- Fix RetailEdge Setup Expense Category filter-coercion crash.

Out of scope:
- Transaction posting changes.
- Branch cascade corrections inside guided transaction dialogs.
- Landed Cost Voucher compatibility.
- Banking upload-template UX.

## Phase 2 — Guided transaction context and branch cascade

Status: implemented; final retail.local replay pending.

Scope:
- Make Sale: Company → Branch → Warehouse cascade, only valid operational branches/warehouses.
- UI gate unmapped warehouse/branch combinations before server validation.
- Update Stock: settings-controlled editability; default checked and read-only unless explicitly enabled.
- Standard Sales Invoice completion blocker resolution.
- Simple Stock Transfer: operational Branch Setup filtering and server revalidation.
- Simple Purchase Invoice: branch cascade and buying-rate resolution from applicable buying price list.
- Cashier Expense: complete the applicable EdgeSuite workflow without redirecting ordinary users to the native DocType.

Safety:
- Submitted accounting/stock documents are never mutated.
- Frontend filtering is guidance only; backend validation remains authoritative.
- Restricted users fail closed.

## Phase 3 — Purchasing and Receive Stock compatibility

Status: implemented and contract-hardened; exact-head automated validation pending.

Scope:
- Fix ERPNext 16.34.x Landed Cost Voucher compatibility without private/removed imports.
- Restore Receive Stock flow.
- Verify Purchase Receipt creation/completion and landed-cost handoff.
- Keep LCV and Purchase Receipt accounting/stock semantics native ERPNext.

## Phase 4 — Banking usability

Status: implemented; exact-head automated validation and retail.local visual replay pending.

Scope:
- Reduce Bank Matching typography and control density now that the EdgeSuite sidebar is present.
- Preserve responsive/mobile usability.
- Upgrade Upload Bank Statement dialog to select an existing reusable RetailEdge bank mapping template or create one through a permission-aware guided path; translate it into ERPNext Bank Statement Import `template_options` so ERPNext remains the import authority.
- Keep bank matching/reconciliation truth and permissions unchanged.

## Phase 5 — Intelligent Hub expansion

Status: pending.

Scope:
- Expand actionable indices for sales, cash, stock, expenses, receivables, payables, branch performance and banking.
- Add action thresholds/settings where required.
- Prioritise exceptions and recommended next actions.
- Keep documents and important reports clickable.
- Propagate Business Hub period/scope consistently.
- Avoid decorative KPIs that do not lead to an action or decision.

## Phase 6 — Second MVP audit and release gate

Status: pending.

Sequence:
1. Run focused tests for Phases 1–5.
2. Run full CI, EdgeSuite compatibility, theme, lint and browser/persona smoke.
3. Perform the required second full MVP re-audit.
4. Close audit gaps.
5. Freeze the audit.
6. Only then perform RC3 persona/browser acceptance.
7. Blocker-only corrections.
8. RetailEdge 1.0.0 release hardening and final gates.

## Report format after each phase

- Exact branch head.
- Files changed.
- Tests/gates run.
- Defects fixed.
- Deferred items.
- Migration/patch impact.
- Next phase only.
