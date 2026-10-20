# RetailEdge MVP-C2 — `retail.local` acceptance evidence

Status: **PENDING — NOT YET EXECUTED**

This file records actual manual evidence for `docs/mvp_c2_physical_merchant_acceptance_20261020.md`. A pending row is not a pass.

## Candidate identity

| Field | Value |
| --- | --- |
| Starting `version-16` SHA | `00e85a98c4d15ebab003af784326d04bdf51f51e` |
| PR #236 merge | confirmed |
| Acceptance PR | #237 |
| RetailEdge deployed SHA | PENDING |
| EdgeSuite UI deployed SHA | PENDING |
| Frappe version | expected `16.52.0`; verify on site |
| ERPNext version | expected `16.51.1`; verify on site |
| POSNext version/SHA | PENDING verification |
| ProcessEdge POSNext Override version/SHA | PENDING verification |
| Site | `retail.local` |
| Acceptance date | PENDING |
| Operator | PENDING |

Do not place passwords, API credentials, encryption keys, customer secrets or sensitive production data in this file.

## Automated-candidate evidence

PR #236 completed exact-head automated validation before merge. PR #237 is documentation-only but must still keep its own relevant repository checks green before merge.

| Gate | PR #237 result |
| --- | --- |
| CI | PENDING |
| Linters / security | PENDING |
| Upgrade Validation | PENDING |
| EdgeSuite UI Candidate Compatibility | PENDING |
| Theme compatibility | path-dependent / verify if run |
| Browser Persona | path-dependent / PR #236 code evidence remains authoritative unless runtime code changes |

Any runtime-code correction discovered during manual acceptance creates a new exact candidate and invalidates reliance on the previous code-head evidence for affected gates.

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
| — | — | — | None recorded yet; acceptance not executed | — | — |

## Acceptance decision

Current decision: **NOT ACCEPTED — manual `retail.local` evidence is still pending.**

Promote this to PASS only when all required rows have passed on one exact deployed candidate, no release-blocking defect remains, and at least one supported 1.0 printing path has been physically accepted.

After PASS, proceed to MVP-C3 — Scale + fresh-install acceptance. Do not tag or publish RetailEdge 1.0 from MVP-C2 alone.
