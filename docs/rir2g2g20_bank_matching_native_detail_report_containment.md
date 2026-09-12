# RIR2G2G20 — Bank Matching Native Detail and Report Containment

## Goal

Keep the active RetailEdge Bank Matching & Reconciliation EdgeSuite workspace fully operational while preventing raw Frappe/ERPNext Form and Query Report escapes for EdgeSuite-only users.

## Runtime finding

The production Page loads `bank_matching_edgesuite_workspace.js` as the active banking workspace.

Older `bank_matching_reconciliation.js` and `bank_match_review_ui.js` files contain legacy native routes but are not loaded by the current Page. They are intentionally left unchanged in this slice.

The active workspace already:
- reads the shared RetailEdge access context;
- stores `canUseNativeDesk`;
- renders Bank Transaction and accounting-document identity as plain text when Native Desk is unavailable;
- gates those native document drill-through actions.

Two residual native escapes remain in the active path:
- the review modal's `Open Audit Record` action opens the raw `RetailEdge Bank Transaction Match` Form without the Native Desk gate;
- Page menu items `Open Matching Report` and `Open Reconciliation Readiness Report` always open native Query Reports.

## Required contract

- Resolve Native Desk capability through the same authoritative Business Hub/master-experience access context already used by RetailEdge.
- Capability resolution must fail closed.
- Reuse one page-lifetime capability promise so the workspace and Page menu cannot disagree because of duplicated access resolution.
- The review modal may expose `Open Audit Record`, `Open Bank Transaction`, and `Open Accounting Document` only when Native Desk is allowed.
- Native Form handlers must independently fail closed.
- Native Query Report menu entries must be added only when Native Desk is allowed.
- EdgeSuite banking setup/readiness Page navigation remains available.
- Bank transaction, match, accounting-document, amount, status and evidence identity remain visible as operational truth.
- The current production Page must continue loading the EdgeSuite workspace, not the legacy reconciliation/review scripts.

## Safety

- No bank candidate scoring, fuzzy matching, approval, confirmation, reconciliation or execution logic changes.
- No Company/Branch/Bank Account scope changes.
- No Bank Transaction, Payment Entry, Journal Entry, Sales Invoice or Purchase Invoice accounting semantics change.
- No auto-submit or submitted-document mutation.
- No role, permission, Branch Assignment or server API change.
- No shared EdgeSuite UI runtime change.
- Legacy unused banking scripts are not rewritten merely to satisfy source scans.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Tests required

- active Page loader points to `bank_matching_edgesuite_workspace.js`;
- legacy reconciliation/review scripts are not part of the active Page loader;
- Native Desk capability resolver uses the shared access context and fails closed;
- workspace state consumes the shared resolver;
- native Form helper fails closed;
- audit-record action is Native-Desk-gated;
- native Query Report menu configuration is Native-Desk-gated;
- banking setup/readiness EdgeSuite Page action remains available;
- matching/reconciliation endpoints and workflow behavior remain untouched.

## Freeze gate

Freeze only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
