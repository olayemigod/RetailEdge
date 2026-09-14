# RetailEdge 1.0.0 — QA and Release Readiness Checklist

## Current authority

- Product: RetailEdge
- Target release: **1.0.0**
- Current state: **QA IN PROGRESS**
- Current QA focus: **Business Hub**
- Business Hub QA status: **ONGOING / NOT YET ACCEPTED**
- Full RetailEdge MVP persona/workflow QA: **NOT YET COMPLETE**
- Tagging/release: **BLOCKED**
- No `v1.0.0` tag exists.
- No GitHub Release exists.
- Automated CI/browser runs are regression evidence and do not replace manual/operational QA acceptance.

## Repository state note

PR #56 was merged to `version-16` as `06b9170edd3150394cf827de3827d171605f0463` before the actual QA stage was complete. That merge must **not** be interpreted as release acceptance. The current `version-16` line is an integration candidate while QA continues.

Do not force-reset or rewrite release-branch history merely to change the status record. Any QA blocker found from this point must be fixed through the existing governed QA line and revalidated before release.

## Actual release order

1. Second full MVP implementation audit — **COMPLETE**
2. Business Hub hardening — **IMPLEMENTED**
3. Business Hub QA — **IN PROGRESS**
4. Close Business Hub P0/P1 QA defects — **PENDING**
5. Re-test Business Hub until accepted — **PENDING**
6. Full RetailEdge MVP QA across personas and operational workflows — **PENDING**
7. Close full-MVP P0/P1 defects — **PENDING**
8. Re-run full persona/browser/permission/accounting/stock acceptance — **PENDING**
9. Freeze RC3 acceptance only after the above is complete — **PENDING**
10. 1.0.0 release hardening/final gates — **PENDING**
11. Tag `v1.0.0` and publish release — **BLOCKED UNTIL QA COMPLETES**

## Business Hub QA scope currently in progress

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

## Full MVP QA still required after Business Hub

Business Hub acceptance does **not** accept the rest of RetailEdge. Separate QA is still required for:

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

## Automated evidence retained

The following are useful regression signals only:

- Browser Persona #234 — 24/24 PASS;
- Browser Persona #235 — 24/24 PASS;
- Theme, lint, CI, EdgeSuite compatibility and upgrade validation runs on the PR #56 candidate;
- release-branch CI #2986 PASS.

They must not be relabelled as Business Hub QA completion, full RC3 acceptance, or release readiness.

## Release rule

**No tag, GitHub Release, production-release declaration, or “RetailEdge 1.0 is complete” statement until Business Hub QA is completed and the subsequent full MVP QA/RC3 sequence is accepted.**
