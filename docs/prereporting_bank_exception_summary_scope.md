# Pre-reporting Bank Exception Summary read-scope contract

## Business goal

Action Centre banking exception counts must never broaden from a restricted blank Branch to all Bank Transaction Match rows in the selected Company. The directly whitelisted summary endpoint must enforce the same Company/Branch reporting scope even when called outside Action Centre.

## B4B24 scope

This slice hardens only `get_bank_exception_summary` and its bounded read of existing `RetailEdge Bank Transaction Match` state. It does not discover candidates, select or rank candidates, lock batch candidates, update Bank Match Review, confirm matches, reconcile documents, or change any banking workflow.

## Read-scope contract

- Company remains mandatory and current-reader Company permission is checked before scope resolution.
- Read permission for `RetailEdge Bank Transaction Match` remains mandatory.
- Explicit Branch is revalidated through `validate_report_scope` and applied as a scalar predicate.
- Restricted blank single/multi Branch scope is applied as an `IN` predicate over the authoritative allowed Branches.
- Restricted-zero, unauthorized Company and invalid explicit Branch scope stop before the match query.
- An unexpected restricted-empty scope cannot remove the Branch predicate.
- Unrestricted global and compatible unrestricted legacy readers preserve the existing Company-wide blank-Branch summary.
- Unattributed blank-Branch match rows are excluded from restricted reads rather than treated as Company-wide.
- Date filters and the 2,000-row scan bound remain unchanged.

## Candidate invariant and preserved composition

The invariant remains:

`selected report row candidate == batch job locked candidate == Bank Match Review candidate == confirmation candidate`

The summary reads only existing decision and execution state. It does not import or call candidate discovery, scoring, selection, locking, review, confirmation, reconciliation or mutation code. Action Centre continues to pass its already-resolved common Company/Branch/date scope and preserves its source key, actions, fingerprints and follow-up composition.

Business Hub and reconciled QA composition remain unchanged.

## Deferred manual QA

Browser/persona validation remains part of the reconciled manual QA pass. Verify Action Centre banking counts and direct endpoint behavior as unrestricted owner, unrestricted legacy manager, restricted single-Branch user, restricted multi-Branch user, restricted-zero user, Company-denied user and invalid explicit-Branch user. Confirm counts change only by scope and no Bank Match Review or candidate state is modified.
