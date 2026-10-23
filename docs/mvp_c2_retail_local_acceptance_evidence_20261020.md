# RetailEdge MVP-C2 — `retail.local` acceptance evidence

Status: **EXACT-HEAD REVALIDATION REQUIRED — MANUAL `retail.local` ACCEPTANCE PENDING**

This file records actual manual evidence for `docs/mvp_c2_physical_merchant_acceptance_20261020.md`. A pending row is not a pass.

## Candidate identity

| Field | Value |
| --- | --- |
| Starting `version-16` SHA | `00e85a98c4d15ebab003af784326d04bdf51f51e` |
| PR #236 merge | confirmed |
| Acceptance PR | #238 |
| Current PR head | read from PR #238 at acceptance; do not copy an older SHA |
| Last fully green runtime SHA | `44df381c563d41e24be697acbffed50645f3b17f` |
| RetailEdge deployed SHA | PENDING local verification |
| EdgeSuite UI deployed SHA | PENDING local verification |
| Frappe version | expected `16.52.0`; verify on site |
| ERPNext version | expected `16.51.1`; verify on site |
| POSNext version/SHA | `1.17.0` / `0b8b6f3bee1b943f6a4982c8d5e987c9421487da`; verify on site |
| ProcessEdge POSNext Extension version/SHA | `0.0.15` / `61a5fb9b92d8b9f4bb003c408474811f62deef3b`; verify on site |
| Site | `retail.local` |
| Acceptance date | PENDING |
| Operator | PENDING |

Do not place passwords, API credentials, encryption keys, customer secrets or sensitive production data in this file.

## Automated-candidate evidence

PR #236 completed exact-head automated validation before merge and remains the merged User Readiness foundation. PR #238 is now the single RetailEdge MVP-C2 runtime/persona/onboarding closure candidate; it contains runtime, role-consolidation, canonical cashier POS permissions, and the governed local POSNext dependency pin.

Runtime SHA `44df381c563d41e24be697acbffed50645f3b17f` passed all five required hosted gates:

| Gate | Last fully green runtime result |
| --- | --- |
| CI | PASS — run #5470 |
| Linters / security | PASS — run #5329 |
| Upgrade Validation | PASS — run #2495 |
| EdgeSuite UI Candidate Compatibility | PASS — run #3585 |
| Browser Persona | PASS — run #2596 |

After that green runtime run, the acceptance evidence was recorded and the candidate baseline was corrected from ProcessEdge POSNext Extension `0.0.14` / `922fd7ba5d4730afc86bcdc05764e4b4b12208dc` to the required authenticated-session compatibility dependency `0.0.15` / `61a5fb9b92d8b9f4bb003c408474811f62deef3b`. Because the baseline pin is part of the candidate contract, the current PR head must pass the full exact-head gate set again before local acceptance can begin.

| Gate | Current PR #238 head |
| --- | --- |
| CI | PENDING replacement exact-head run |
| Linters / security | PENDING replacement exact-head run |
| Upgrade Validation | PENDING replacement exact-head run |
| EdgeSuite UI Candidate Compatibility | PENDING replacement exact-head run |
| Browser Persona | PENDING replacement exact-head run |

Any runtime-code, migration, baseline, or evidence change that moves the candidate head requires replacement exact-head validation before that new head can be accepted.

## Physical / merchant acceptance

Use exact document names and concise evidence references in Notes where useful.

| # | Area | Case | Persona | Result | Documents / evidence | Notes |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | Preflight | Confirm exact deployed RetailEdge/EdgeSuite/platform versions | Manager/Admin | PENDING |  |  |
| 2 | Preflight | Migrate, build, clear cache, hard refresh | Manager/Admin | PENDING |  |  |
| 3 | Readiness | Intended operational user is Ready for assigned Company/Branch | Manager/Admin | PENDING |  |  |
| 4 | Readiness | Intentionally incomplete user remains fail-closed with repair guidance | Manager/Admin | PENDING |  |  |
| 5 | Cashier | Open shift | Cashier | PENDING |  |  |
| 6 | Selling | Create normal sale | Cashier/Sales | PENDING |  |  |
| 7 | Selling | Cash payment | Cashier/Sales | PENDING |  |  |
| 8 | Selling | Non-cash or mixed payment | Cashier/Sales | PENDING |  |  |
| 9 | Selling | Edited price/tax/discount reflected in totals | Cashier/Sales | PENDING |  |  |
| 10 | Context | Correct Branch and cashier/user attribution | Cashier | PENDING |  |  |
| 11 | Printing | Produce receipt through supported 1.0 path | Cashier | PENDING |  |  |
| 12 | Printing | Receipt readable; submitted document unchanged | Cashier | PENDING |  |  |
| 13 | Expense | Record cashier expense | Cashier | PENDING |  |  |
| 14 | Cash | Record governed cash deposit/removal | Cashier/Manager | PENDING |  |  |
| 15 | Cash | Expected cash reflects expense/deposit policy | Manager | PENDING |  |  |
| 16 | Return | Return / credit note against original sale | Sales/Manager | PENDING |  |  |
| 17 | Receivables | Record customer payment | Accounts/Sales | PENDING |  |  |
| 18 | Stock | Stock count / adjustment | Stock user | PENDING |  |  |
| 19 | Stock | Stock transfer | Stock user | PENDING |  |  |
| 20 | Stock | Verify quantities and Branch/warehouse scope | Stock user | PENDING |  |  |
| 21 | Permissions | Cross-Company/Branch attempt denied | Operational user | PENDING |  |  |
| 22 | Purchasing | Create standard purchase journey | Purchase user | PENDING |  |  |
| 23 | Purchasing | Complete receipt and Purchase Invoice progression | Purchase user | PENDING |  |  |
| 24 | Payables | Record supplier payment | Accounts/Purchase | PENDING |  |  |
| 25 | Accounting | Confirm ERPNext remains authoritative for posting | Accounts/Manager | PENDING |  |  |
| 26 | Cashier | Close shift and enter actual cash | Cashier | PENDING |  |  |
| 27 | Reconciliation | Opening + sales - expenses - deposits vs closing cash | Manager | PENDING |  |  |
| 28 | Reconciliation | Shortage/overage behavior where exercised | Manager | PENDING |  |  |
| 29 | Integrity | Revisit/read surfaces create no duplicate posting | Manager | PENDING |  |  |
| 30 | Reporting | Business Hub and required reports match journey documents | Manager | PENDING |  |  |
| 31 | Cascades | Company -> Branch filters clear invalid stale child context | Manager | PENDING |  |  |
| 32 | Permissions | Unauthorized Advanced/direct API access remains denied | Restricted user | PENDING |  |  |

## Printing support evidence

RetailEdge 1.0 does not require WebUSB physical acceptance under the current support boundary.

At least one supported merchant path must pass:

| Printing path | Required for MVP-C2? | Result | Evidence / notes |
| --- | --- | --- | --- |
| Normal system printing / Print Document | acceptable supported path | PENDING |  |
| Serial / Bluetooth direct printing | acceptable supported path when configured | PENDING |  |
| WebUSB preview | no | NOT RUN / OPTIONAL | physical preview matrix remains separate |

## Hard-stop defect log

| ID | Case | Severity | Description | Corrective PR/SHA | Retest result |
| --- | --- | --- | --- | --- | --- |
| C2-001 | Cashier / Start POS | Release blocker | Canonical cashier lacked `Account` read/select and POS Opening/Closing Shift operational permissions; PR #238 now carries a bounded canonical-role migration bridge. | PR #238 | PENDING local retest |
| C2-002 | Start POS session handoff | Release blocker | POSNext 1.17.0 could redirect a valid Frappe session to `/pos/account/login` after a non-auth logged-user startup failure; ProcessEdge POSNext Extension PR #24 carries the bounded compatibility bridge. | Extension PR #24 | PENDING local retest |
| C2-003 | Candidate baseline | Release blocker | PR #238 still pinned ProcessEdge POSNext Extension 0.0.14 even though C2-002 requires 0.0.15. The candidate baseline is now corrected to 0.0.15 / `61a5fb9b92d8b9f4bb003c408474811f62deef3b`. | PR #238 | PENDING exact-head + local verification |

## Acceptance decision

Current decision: **NOT ACCEPTED — the baseline now matches the required POS runtime dependency, but replacement exact-head validation and manual `retail.local` evidence are pending.**

Promote this to PASS only when all required rows have passed on one exact deployed candidate, no release-blocking defect remains, and at least one supported 1.0 printing path has been physically accepted.

After PASS, proceed to MVP-C3 — Scale + fresh-install acceptance. Do not tag or publish RetailEdge 1.0 from MVP-C2 alone.
