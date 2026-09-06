# RetailEdge RIR2B3 — Banking Readiness controlled discoverability

## Checkpoint

- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Starting head: `39688f27a6c8cf2c0d206a49ef4a36e9223d8feb`
- RIR2B3A status: Banking Readiness inventory read scope hardened and exact-head gates green.
- RIR2B3B scope: controlled Business Hub discoverability only.

## Decision

`banking-readiness` is promoted dynamically into the primary EdgeSuite Business Hub Money group only when the current reader can open the Page through Frappe Page permission. It appears immediately before Bank Matching so setup/readiness precedes operational matching.

The compact native Frappe workspace remains unchanged. It is a fallback shell and does not need to duplicate this permission-aware operational promotion.

`branch-assignments` remains reachable only through the System Manager-only consolidated RetailEdge Setup. No duplicate Business Hub route is added and Setup roles are not broadened.

## Safety

This slice changes route composition only. It does not change:

- Bank Account data or configuration semantics;
- Banking Readiness calculations or read-scope enforcement;
- Bank Matching discovery, scoring, locking, review or reconciliation;
- Payment Entry, GL or accounting behaviour;
- Branch Assignment authority or restricted-zero fail-closed semantics;
- the compact workspace composition;
- the reconciled QA branch structure;
- reporting implementation or manual persona QA status.

The Banking Readiness backend remains responsible for Company/Branch permission enforcement. Navigation permission filtering is an additional presentation boundary, not the security boundary.
