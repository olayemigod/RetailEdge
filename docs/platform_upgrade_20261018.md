# ProcessEdge v16 candidate — 18 October 2026

Candidate only. Keep PR #226 draft until manual `retail.local` QA. Working bench promotion is pending automated acceptance; its original code and database remain available for rollback.

## Immutable baseline

`platform-baseline.json` records the runtime and dependency commits. Frappe 16.52.0 requires Python 3.14 and Node 24. ERPNext 16.51.1 declares Frappe >=16.50,<17. Tested runtime: Python 3.14.4, Node 24.15.0, Yarn 1.22.22.

RetailEdge incorporates authoritative `version-16` base `b95de8f81d6dfc4de6da53514277ca3504439a19`. EdgeSuite incorporates authoritative main `f5e1b05b4c5a0a9c511b78ba93ddaa63f5f6dfa6`; candidate PR #43 is pinned at `2a87d780dd19424aed24f35f9f988b050dfa9712`. Approved responsive SmartDate behavior is preserved.

Payments is a test dependency on the clean integration site, not a new merchant-site app. Its supported version-16 commit is pinned: current develop requires Frappe 17 and was rejected for this candidate.

## Isolated migration evidence

Original bench `/home/olayemigod/frappe-bench`; separate staging bench `/home/olayemigod/retail-v16-upgrade-20261018`; restored site `retail-v16-stage.localhost`. Six installed merchant apps: Frappe, ERPNext, EdgeSuite, RetailEdge, POSNext and ProcessEdge POSNext override. Other directories in the original bench are not installed-site dependencies.

Backup prefix: `sites/retail.local/private/backups/20261018_162125-retail_local-` in the original bench. Database, public/private files and configuration backed up; encryption key preserved privately. Staging uses separate databases, Redis ports, web port, paused scheduler and muted mail.

Two migrations and the initial six-app production build passed with EdgeSuite unchanged. Ledger fingerprints before and after migrations match exactly:

- GL Entry: 170 rows, SHA256 `6a6997ff2a60415ce17acb1777a547eb61204f318ffe67732796a7ee6c511a9f`.
- Stock Ledger Entry: 27 rows, SHA256 `a37548076242ffe8c308f11382bfcdaba94cb5d9bc288d99606869c0a4dd8722`.

Authenticated HTTP login, ping, current-user, Desk and Business Hub probes passed. Upstream Warehouse Stock Manager Read is present after migration in native and custom permissions. No Stock User workaround was added.

## Bounded changes and failures fixed

EdgeSuite PR #43 adapts supported native controls with feature detection and fallback. The v16 Desk dock is mounted outside the old sidebar; suppress it only while an opted-in EdgeSuite shell owns navigation. Light/dark, keyboard, late mount and native-route restoration regressions cover the fix. No broad redesign or private native component import.

Retail test isolation repairs prevent live merchant context, accounting settings, invoice data and broad database mocks from contaminating test fixtures. Browser seeding now uses the merchant's governed price-list resolution. Printing browser tests accept a supplied administrator password. These changes do not widen production permissions.

The full Retail suite passed before final base reconciliation: 3,056 tests, 23 skips. Final reconciled-head rerun and the complete 46-case browser matrix remain acceptance gates. Initial browser run passed 44; two printing failures identified the hardcoded administrator password and were corrected before final rerun.

EdgeSuite final candidate: production build, npm contracts, 218 Python contracts and Ruff passed. All four exact-head GitHub checks passed. Earlier real-site integration covered 17 tests and the browser suite 19 tests; repeat checks against final candidate are recorded with final release evidence.

POSNext runtime is unchanged at the manifest SHA. Its tests require a staging-only overlay under the user-approved canonical ProcessEdge skill: explicit synchronous database mocks for Python 3.14 and an updated empty-input assertion plus a no-query regression. Reproducible patch: `qa/posnext-v16-test-compatibility.patch`. The clean integration site temporarily enables native duplicate-item fixture behavior and restores it afterwards; merchant settings are unchanged. All 37 POSNext tests pass with this disclosed overlay. The ProcessEdge override's pytest suite passed 69 tests.

## Acceptance and promotion

Do not treat package constraints or an older CI run as final proof. Run the manifest verifier, joint dependency check, full Retail tests, EdgeSuite integration/browser/theme checks, complete Retail permission/persona/browser matrix and all required GitHub gates on the final published PR head. Preserve draft status and perform manual `retail.local` QA only after the automated candidate is proven. Local logs are under the isolated bench's `logs/`; credentials and browser traces are not committed.
