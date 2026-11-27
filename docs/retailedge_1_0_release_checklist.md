# RetailEdge 1.0.0 — QA and Release Readiness Checklist

## Post-merge correction — 26 November 2026

**This checklist preserves the historical PR #58 / RC5 snapshot. It is not the current release authority.** Repository merges completed under RetailEdge [PR #250](https://github.com/olayemigod/RetailEdge/pull/250) at `b636632fd12bc01a9f1abee08bbf65922e8c245f` and POSNext Extension [PR #26](https://github.com/olayemigod/Processedge-POSNext-Extension/pull/26) at `374f517064755cfa56f20e8740a00721210d1f96`. Both merged heads passed their post-merge CI. The five RetailEdge exact-head gates and two cross-app Extension gates also passed on tree-identical pre-merge heads.

**Not released to any site by this GitHub action.** Actual Production deployment, formal tagging/GitHub Release, backup restoration, hosted auto-update settings and staging acceptance are separate gates requiring verification/authorization. Historical PR #58 SHA and older run IDs below remain evidence of that earlier freeze, **not** instructions to deploy or merge those commits.

For the current immutable commits, dependency distinctions, automated evidence and staging/rollback checklist, use [RC3 Post-Merge Deployment Readiness](release/rc3_postmerge_deployment_readiness_20261126.md) and its [release evidence inventory](release/rc3_repo_merge_inventory_20261126.json). Follow [Issue #251](https://github.com/olayemigod/RetailEdge/issues/251) for the unapproved hosted-site gates.

## CI reconciliation — 27 November 2026

After the original RetailEdge RC3 merge at `b636632fd12bc01a9f1abee08bbf65922e8c245f`, an unchanged-baseline CI rerun exposed test-fixture failures. Test-only [PR #254](https://github.com/olayemigod/RetailEdge/pull/254) resolved them and passed **7/7 exact-head checks** on `3b6751329d59c85cf39710eb1912f39fc101a7d1`. PR #254 was merged and the verified RetailEdge `version-16` branch head became `f46040f7d3822d306576a31a68bfe267b7a101f1`. [Issue #253](https://github.com/olayemigod/RetailEdge/issues/253) is closed. This correction touches **five test files only** and does not alter the original release candidate's runtime behavior. Keep original PR #250 and POSNext Extension #26 merge SHAs as historical checkpoints, not as the latest RetailEdge branch head.

**No site deployment, staging restore, Production acceptance, tag or GitHub Release is implied or authorized.** Track those separately under [Issue #251](https://github.com/olayemigod/RetailEdge/issues/251).

## Historical authority — superseded RC5 snapshot

- Product: RetailEdge
- Target release: **1.0.0**
- Authoritative PR: **#58**
- PR base: `version-16`
- Frozen audit/release-candidate head: `85c1834aedf5a934458a04a706cdc4d10ea0f02f`
- Current state: **RC5 — FINAL RELEASE HARDENING**
- Second MVP audit: **FROZEN / COMPLETE**
- Business Hub → reporting audit: **FROZEN / COMPLETE**
- Formal RC3 browser/persona acceptance: **PASS — 31/31**
- Exact-head governed gates: **6/6 GREEN**
- Tagging/release: **PENDING FINAL PROMOTION DECISION**
- No `v1.0.0` tag exists.
- No GitHub Release exists.

Exact-head gate record:

- RetailEdge Theme Compatibility — run **#1660** — PASS
- Linters / Semgrep / dependency audit — run **#3711** — PASS
- clean Frappe v16 CI — run **#3735** — PASS
- EdgeSuite UI Candidate Compatibility — run **#1967** — PASS
- RetailEdge Upgrade Validation — run **#877** — PASS
- Browser Persona Smoke / formal RC3 — run **#981** — **31/31 PASS**

## Repository state note

Earlier PR #55 / PR #56 audit and browser records remain historical evidence. PR #58 is the current release-hardening authority. Do not force-reset or rewrite release-branch history merely to alter status records.

From the PR #58 audit freeze forward, only release-blocking corrections may change the candidate. Any code change invalidates exact-head release evidence and requires the governed gates to be rerun before promotion.

## Actual release order

1. Second full MVP implementation audit — **COMPLETE**
2. Business Hub hardening — **COMPLETE**
3. Business Hub → reporting drill/security audit — **COMPLETE**
4. Close audit P0/P1 findings — **COMPLETE**
5. Freeze audit candidate — **COMPLETE**
6. Formal RC3 browser/persona acceptance — **COMPLETE — 31/31 PASS**
7. Close RC3 blocker-only findings and revalidate — **COMPLETE**
8. Exact-head Theme/Lint/CI/EdgeSuite/Upgrade/RC3 gates — **COMPLETE — 6/6 GREEN**
9. 1.0.0 release documentation/promotion hardening — **COMPLETE**
10. Mark governed PR ready / merge or promote through the approved `version-16` path — **PENDING APPROVAL**
11. Tag `v1.0.0` and publish GitHub Release — **PENDING APPROVAL**

## Historical QA scope — completed on PR #58

The checklist below is retained as the acceptance scope that was exercised and closed. It is no longer an open QA backlog.

### Business Hub acceptance scope

Business Hub QA must cover, at minimum:

- shell stability and Back/Forward behaviour;
- Company/Working Branch context and cascades;
- the eight actionable business indices;
- date/period filters and hand-off into reports;
- Attention/priority signals and drill-through;
- quick actions and guided transaction entry points;
- permissions and restricted-zero behaviour;
- Company/Branch isolation;
- loading, empty, unavailable and error states;
- light/dark mode and responsive layouts;
- no native-Desk escape where EdgeSuite owns the workflow;
- no permission/modal leakage;
- browser console/network/runtime errors;
- practical usefulness of the Hub to owners/managers, not merely successful rendering.

## Historical full-MVP QA scope — completed by formal RC3

Business Hub acceptance alone did not accept the rest of RetailEdge. The following broader scope was subsequently exercised through the governed full-suite, permission/upgrade checks and formal RC3 browser/persona acceptance, and is now closed for the frozen candidate:

- Selling and customer workflows;
- Purchasing / Receive Stock;
- payments, cash and banking;
- Business Expenses and Cashier Expense;
- stock transfer, adjustment, position and movement;
- Action Centre and operational review pages;
- receivables/payables;
- reporting and management visibility;
- role/persona access;
- one/multiple/zero Branch rules;
- permission manipulation and cross-Company/Branch isolation;
- workflow-enabled completion;
- ERPNext accounting/stock integrity;
- advanced-native boundaries;
- install/migration/upgrade behaviour.

## Exact-head acceptance evidence

The authoritative PR #58 frozen head `85c1834aedf5a934458a04a706cdc4d10ea0f02f` completed all governed release-candidate gates successfully. Browser Persona run #981 executed 31 tests and completed **31/31 PASS**.

Historical PR #55/#56 browser runs remain useful regression history but are not the current release authority.

## Release rule

**Do not create the `v1.0.0` tag, publish a GitHub Release, merge/promote the governed candidate, or declare production release until the final promotion decision is explicitly approved.** If the frozen candidate changes, rerun the exact-head governed gates before promotion.
