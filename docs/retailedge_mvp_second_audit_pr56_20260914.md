# RetailEdge 1.0 — PR #56 Second Full MVP Re-Audit

## Authority

- Product: RetailEdge
- Release target: **1.0.0**
- Authoritative PR: **#56**
- Authoritative branch: `qa/retailedge-visual-identity`
- PR base: `version-16`
- Validated gap-closure implementation head: `aea2cf4980cfd2dc2b61133ee567f166392a7285`
- Audit date: 2026-09-14
- Audit state: **FROZEN — IMPLEMENTATION GREEN / FORMAL RC3 READY**

This is the required second full MVP re-audit for the current PR #56 candidate. It supersedes the older PR #55 audit for the purpose of accepting the visual/runtime, Business Hub, guided-context, Receive Stock, banking-import and intelligence changes introduced after the prior release candidate.

Browser/persona runs triggered before this audit is frozen are regression evidence only and **must not** be counted as formal RC3 acceptance.

## Governing conclusion

No new P0 product, accounting, stock, permission, branch-isolation, install or upgrade defect was found.

Four P1 audit/acceptance gaps were found and closed:

1. the legacy Business Hub MVP contract still asserted the pre-Phase-5 four-signal Operate layout;
2. the RC3 runbook still named PR #55 and its historical PASS as current authority;
3. the RC3 browser suite did not explicitly exercise the PR #56 Business Hub intelligence, browser Back/Forward shell recovery, or shared Working Branch switcher;
4. the Business Hub snapshot required raw Company read permission even for canonical RetailEdge global managers, contradicting the shared RetailEdge global-branch-access contract.

The product implementation itself remains ERPNext/Frappe-authoritative for accounting, stock, workflow and permissions.

## Twelve-area MVP review

| # | Review area | Audit status | PR #56 conclusion |
|---|---|---|---|
| 1 | Release candidate composition | GREEN | PR #56 is directly based on `version-16`, is mergeable, and is the single current hardening line. No divergent product branch is required. |
| 2 | Role model / EdgeSuite access / branch context | GREEN | Canonical RetailEdge roles remain stable. EdgeSuite-only containment is presentation-level only. The top-bar Working Branch switcher is fed by permission-aware allowed branches and posts through server-side `switch_operating_context`. Restricted-zero remains explicit and fail-closed. |
| 3 | Sales / customer workflow | GREEN | Guided Sales Invoice remains draft-first, Company→Branch→Warehouse is server revalidated, Update Stock policy is settings-controlled, and standard completion preserves active Frappe Workflow precedence and native ERPNext `submit()`. |
| 4 | Purchasing / Receive Stock / supplier workflow | GREEN | Guided Purchase Invoice remains draft-first with server-resolved buying context. Receive Stock uses the ERPNext PO→Purchase Receipt mapper and native Purchase Receipt submit. LCV uses ERPNext v16-compatible native mapping/validation. |
| 5 | Payments / cash / banking | GREEN | Existing payment/cash authorities remain intact. Bank Matching remains EdgeSuite-owned for everyday work. Upload Statement creates native ERPNext Bank Statement Import records; reusable mapping templates are permission-aware and Company/Bank/Branch-context checked before writing native `template_options`. |
| 6 | Expenses | GREEN | Business Expense remains the modern owner/manager/accounts flow. Cashier Expense remains a governed draft-first cashier flow and now continues into EdgeSuite workflow completion rather than forcing ordinary users into the native DocType. |
| 7 | Stock operations | GREEN | Guided Stock Transfer remains ERPNext Stock Entry draft truth, with Source/Destination Branch required where configured and both Warehouses revalidated server-side. Complex Serial/Batch cases retain the advanced ERPNext boundary. |
| 8 | Business Hub / command centre | GREEN | Business Hub is the RetailEdge app home, shell ownership is stable across history navigation, quick actions remain permission-derived, canonical RetailEdge global managers use the shared Company-access contract, and Phase 5 exposes eight actionable indices: Sales, Cash, Stock, Expenses, Receivables, Payables, Branch Performance and Banking. |
| 9 | Action Centre / operational review ownership | GREEN | Action Centre remains the EdgeSuite review surface. Banking and other supported review destinations retain current canonical Pages and Native Desk capability boundaries. |
| 10 | Reporting / management visibility | GREEN FOR MVP | Existing reporting authorities are reused rather than reimplemented. Business Hub carries Company/Branch/period handoffs into reports and prioritises actionable exceptions instead of decorative duplicate analytics. |
| 11 | Security / install / migration / upgrade | GREEN AUTOMATED | Exact-head clean Frappe v16 CI, lint/Semgrep/dependency audit, EdgeSuite compatibility, theme checks and real frozen-baseline upgrade validation were green before audit-contract closure. Upgrade validation runs on every PR candidate and verifies submitted accounting truth after double migration. |
| 12 | Acceptance / release governance | GREEN AFTER GAP CLOSURE, REVALIDATION PENDING | RC3 authority is now PR #56 and the browser suite explicitly covers PR #56 intelligence, Back/Forward shell recovery and the Working Branch control. Formal RC3 may count only after this audit is frozen. |

## P1 closure record

### P1-A — stale Business Hub acceptance assertion — CLOSED

The old MVP Home test expected the pre-Phase-5 Stock/Banking/Branch/Cash Shift array. Phase 5 deliberately replaced that display contract with eight action-oriented business indices. The acceptance test now follows the approved Phase 5 contract rather than contradicting it.

### P1-B — stale RC3 authority — CLOSED

`docs/rir2e_consolidated_browser_persona_qa.md` now:

- names PR #56 / `qa/retailedge-visual-identity` as current authority;
- treats the old PR #55 PASS as historical evidence only;
- prohibits counting pre-audit browser triggers as PR #56 RC3 acceptance;
- includes the current Business Hub intelligence and Working Branch contracts.

### P1-C — missing PR #56 browser regression coverage — CLOSED

The consolidated RC3 Playwright spec now explicitly checks:

- all eight Business Hub intelligence cards render for the manager persona;
- browser Back/Forward restores the Business Hub / Action Centre EdgeSuite shell without manual refresh;
- the multi-Branch persona receives an enabled shared Working Branch control showing the active permitted Branch.

These checks supplement, rather than replace, the existing one/multiple/zero Branch API fixtures, role/page access, appearance, mobile, Create/search and operational Page coverage.

### P1-D — RC3 manager operating context was not deterministic — CLOSED

The first gap-closure browser run proved that the manager login had no initial Company context: Frappe's own session-default endpoint returned a null Company, so the Business Hub correctly did not request its scoped snapshot. The multi-Branch fixture still worked because Branch Assignment supplied its context.

The RC3 fixture gives the manager one primary Lagos Branch Assignment to establish deterministic initial Company/Branch context. Exact-head revalidation then exposed the remaining resolver defect: `_resolve_fallback_context` skipped Branch Assignment anchoring for global-access roles, so the Business Hub context reported `operating_context_source = branch_assignment` while still returning an empty Company and Branch.

The resolver now permits a deterministic primary/sole Branch Assignment to supply the **initial** Company/Branch anchor for global RetailEdge managers. This does **not** restrict the manager's effective operational branch scope: `get_operational_branch_scope` still takes the global-access path first and remains unrestricted. Restricted users retain Branch Assignment authority and the restricted-zero fail-closed case.

### P1-E — canonical RetailEdgeManager Business Hub Company access — CLOSED

The new PR #56 browser coverage exposed that a canonical `RetailEdgeManager` could open Business Hub but its Home snapshot failed because the snapshot applied raw `Company` DocType read permission after the shared branch-scope resolver had already classified the role as global RetailEdge access.

Business Hub now follows the same shared access contract used by Operating Context: an already-authorised RetailEdge global-access role may view the selected Company Home snapshot even when that custom role does not carry ERPNext's generic Company read permission directly. Restricted users still require their existing permission/Branch rules and restricted-zero remains fail-closed.

## Safety recheck

The PR #56 hardening does **not**:

- mutate submitted Sales Invoices, Purchase Invoices, Payment Entries, Purchase Receipts or Stock Entries;
- write GL Entry or Stock Ledger Entry directly;
- bypass Frappe permissions for operational actions;
- convert restricted-zero Branch scope into unrestricted access;
- replace ERPNext accounting, stock, reconciliation or Bank Statement Import authority;
- introduce a duplicate reporting engine.

The only new setting introduced by Phase 5 is a Business Hub variance tolerance used for prioritisation only.

## Migration / backward compatibility

- Internal app/module identities remain unchanged.
- The Business Hub intelligence setting is added through an idempotent Custom Field patch.
- Existing reporting settings patch runs before the Business Hub setting patch.
- Upgrade validation starts from the frozen pre-MVP baseline, seeds representative accounting data, switches to the exact candidate, builds, migrates twice, verifies submitted accounting truth, and runs the current RetailEdge suite.
- CoreEdge is not required on the standalone RetailEdge validation site.

## Audit freeze gate — SATISFIED

The validated gap-closure implementation head `aea2cf4980cfd2dc2b61133ee567f166392a7285` passed every required pre-freeze gate:

1. RetailEdge Theme Compatibility — run **#1119** — **PASS**;
2. Linters / Semgrep / dependency audit — run **#2960** — **PASS**;
3. clean Frappe v16 CI — run **#2981** — **PASS**;
4. EdgeSuite UI Candidate Compatibility — run **#1216** — **PASS**;
5. RetailEdge Upgrade Validation — run **#126** — **PASS**, including double migration and submitted accounting-truth verification;
6. Browser Persona Smoke — run **#232** — **PASS** as pre-freeze regression evidence.

The earlier integration failures on head `c370ce66012199f2d55d051d026108f96abf9b2f` were caused by one stale source-contract assertion after the approved global-access resolver refactor. The runtime/browser fix itself was already green. The stale assertion was aligned in `aea2cf4980cfd2dc2b61133ee567f166392a7285`, after which all six gates passed.

This second full MVP audit is now **FROZEN — IMPLEMENTATION GREEN / FORMAL RC3 READY**. Browser run #232 remains pre-freeze regression evidence and is not promoted retroactively to formal RC3.

## Governed release order

1. Second full PR #56 MVP re-audit — **COMPLETE**
2. Close audit P1 gaps — **COMPLETE**
3. Exact-head gap-closure revalidation — **COMPLETE / ALL SIX GATES GREEN**
4. Freeze audit — **COMPLETE**
5. Execute formal RC3 browser/persona acceptance on the frozen audit line — **NEXT**.
6. Fix **only** P0/P1 RC3 defects.
7. Revalidate blocker-only corrections.
8. Complete RetailEdge 1.0.0 release hardening/final promotion gates.
9. Merge/promote through the governed `version-16` path and tag `v1.0.0`.

## Release rule

Do not reopen feature scope between audit freeze and RC3. Additional analytics, cosmetic polish and non-blocking convenience work remain post-1.0 unless a P0/P1 correctness defect is found.
