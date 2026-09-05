# RetailEdge RIR2B1 Route / Promotion Matrix

## Status

- **Phase:** RIR2B1 — current route/promotion matrix freeze
- **Authoritative line:** PR #55 / `qa/retailedge-reconciled-20260902`
- **Source head audited before this document:** `07d00925176fbfe181c60b4ca161e06a03264e6d`
- **Scope:** route/composition audit and freeze only
- **Route changes in RIR2B1:** none
- **Reporting:** remains blocked
- **Manual browser/persona QA:** remains deferred to RIR2E
- **Business Hub redesign:** out of scope; the current Business Hub remains the product home until the post-reconciliation MVP enhancement

RIR2B1 freezes what RetailEdge exposes today, what current RetailEdge Pages already exist, and which destinations are safe candidates for later promotion. It deliberately separates **route composition** from business logic. A Page existing in the repository is not by itself permission to promote it.

## Source-of-truth hierarchy for this matrix

The effective product navigation is composed from three current sources:

1. `retailedge/edgesuite_ui.py` — base EdgeSuite Business Hub groups and permission-aware targets.
2. `retailedge/master_experience.py` — current Business Hub promotions/additions, including Operating Context, Transaction Workspace, Professional Selling, Professional Purchasing, Document Output & Sharing, Payment Management, Projects, browser-approved R4 Pages, and consolidated Setup.
3. `retailedge/workspace_home.py` — compact native Frappe workspace fallback. It is not the primary everyday shell, but it remains a supported fallback and must not silently contradict a deliberately promoted route.

The Business Hub remains the primary product shell. The native workspace is a compact fallback. Native DocTypes and Query Reports remain valid advanced/fallback destinations where RetailEdge has not proven an equivalent everyday Page.

## Decision vocabulary

| Decision | Meaning |
| --- | --- |
| `KEEP_PAGE` | Current RetailEdge Page is already the intended everyday route. |
| `KEEP_GUIDED` | Everyday work should start through the current guided RetailEdge surface; native document remains the ERPNext authority/fallback. |
| `KEEP_NATIVE` | No proven RetailEdge replacement exists; keep the native ERPNext DocType/Report route. |
| `PROMOTE_B2` | Confirmed RIR2B2 route correction. No business-engine rewrite. |
| `REVIEW_B3` | A current RetailEdge Page exists or may improve the route, but promotion requires bounded parity/access/browser evidence first. |
| `DEFER_PARITY` | Promotion is explicitly blocked by an existing parity gate. |
| `ADVANCED_ONLY` | Keep as native/advanced administration/accounting capability rather than making it an everyday EdgeSuite workflow. |
| `MVP_CONDITIONAL` | Keep code; final MVP feature registry may switch it off for a client without deleting reconciled work. |

## Non-negotiable route safety rules

- ERPNext remains the source of truth for accounting, stock, selling, purchasing, payments, projects and submission state.
- A route promotion must not change posting, allocation, reconciliation, pricing, stock valuation, document lifecycle or submission semantics.
- Submitted accounting/stock/payment documents must never be mutated to make a RetailEdge route work.
- Branch Assignment history remains authoritative when it exists; restricted-zero scope remains fail-closed.
- Company, Branch, Warehouse and dependent business context remains server-authoritative.
- EdgeSuite-only presentation must not weaken Frappe/ERPNext permissions.
- Ordinary EdgeSuite-only users must not be forced into native Desk to complete a workflow already declared supported for them.
- Native advanced fallback may remain for users whose EdgeSuite access context allows native Desk.
- Do not merge or cherry-pick an old navigation branch to implement a route decision.
- Do not redesign Business Hub during RIR2B1–RIR2D.

---

# Effective route matrix

The `Current target` column describes the effective current Business Hub route after `master_experience.py` transformations where applicable. `Native fallback` records the current advanced ERPNext/native path or the compact workspace path where it intentionally remains useful.

## Home / operating context

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Product home | `Page: retailedge-business-hub` | Same | Active; RIR runtime blockers now repaired/verified by automation, final persona QA pending | `KEEP_PAGE` | Native RetailEdge workspace is compact fallback | EdgeSuite everyday | Core ON |
| Company / Branch operating context | `Page: operating-context` when Page permission allows | Same | Current master-experience promotion; server-authoritative operating context remains required | `KEEP_PAGE` | Native defaults/setup only for advanced administration | EdgeSuite everyday | Core ON for multi-context users |
| Universal Create | Product menu -> Business Hub Create | Current Business Hub guided Create | Incorporated active; fuzzy/searchable Create already present | `KEEP_GUIDED` | Native forms only where advanced fallback is explicitly supported | EdgeSuite everyday | Core ON |

## Sell

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Transaction starting point | `Page: transaction-workspace` | Same | Current promotion; Frappe v16 fullname runtime defect repaired in RIR2A1 | `KEEP_PAGE` | Native documents only as permitted | EdgeSuite everyday | Core ON |
| Professional selling | `Page: professional-selling` | Same | Current promotion; operational-guard asset/load contract verified in RIR2A2; browser persona QA pending | `KEEP_PAGE` | Quotation/Sales Order/Delivery Note native forms for advanced users | EdgeSuite everyday + advanced fallback | Core ON where selling workflow is used |
| Document output / sharing | `Page: document-output-sharing` | Same | Current promotion; ERPNext Print Formats and permissions remain authority | `KEEP_PAGE` | Native Print/Email/attachments where authorised | EdgeSuite everyday | Core ON |
| POS start | Runtime-resolved POS URL/Page | Current POS runtime resolver | Existing provider-aware contract | `KEEP_NATIVE` runtime target | Provider-native POS | Everyday cashier | Core ON if POS deployed |
| Sales Invoice creation | Guided `New Sales Invoice`; base/native list remains `DocType: Sales Invoice` | Guided Create / Transaction Workspace | Guided draft path incorporated active | `KEEP_GUIDED` | Native Sales Invoice list/form for advanced users | EdgeSuite everyday + advanced fallback | Core ON |
| Sales Orders | `DocType: Sales Order` plus Professional Selling orchestration | `professional-selling` | Professional Selling exists; full document remains ERPNext authority | `KEEP_GUIDED` for supported flow; retain native advanced route | Native Sales Order | Mixed | Core/conditional by client workflow |
| Delivery Notes | `DocType: Delivery Note` plus Professional Selling orchestration | `professional-selling` | Same bounded selling orchestration | `KEEP_GUIDED` for supported flow; retain native advanced route | Native Delivery Note | Mixed | Core/conditional by client workflow |
| Sales team / targets | `Page: sales-team-control` | Same | Current Page | `KEEP_PAGE` | Sales Person/Partner masters and native target reports | Role/permission gated | MVP conditional |
| Sales Person / Partner masters | Native DocTypes | No safer full replacement proven | Master/configuration records | `KEEP_NATIVE` | Same | Advanced/manager | MVP conditional |
| Commission / target detail reports | Native ERPNext Reports | No replacement required | Native analytical truth | `KEEP_NATIVE` | Same | Manager/advanced | MVP conditional |
| POS Opening / Closing | Runtime-resolved native DocTypes | No replacement required by current contract | Provider/runtime dependent | `KEEP_NATIVE` | Same | Cashier/manager | Core ON if POS deployed |

## Pricing & Promotions

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pricing & Promotions overview | `Page: pricing-promotions-control` | Same | Current control Page | `KEEP_PAGE` | Native masters below | EdgeSuite manager | MVP conditional |
| Price Lists / Item Prices / Pricing Rules | Native DocTypes | Overview Page exists, but ERPNext masters remain source of truth | No evidence to replace full configuration forms | `KEEP_NATIVE` | Same | Advanced/manager | MVP conditional |
| Promotional Schemes / Coupon Codes / Loyalty Programs | Native DocTypes | Overview Page exists | No complete RetailEdge replacement proven | `KEEP_NATIVE` | Same | Advanced/manager | MVP conditional / feature-off capable later |

## Buy

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Professional purchasing | `Page: professional-purchasing` | Same | Current promotion; EdgeSuite-only guard contract verified; bounded browser/persona QA still required | `KEEP_PAGE` | Native buying forms/reports for advanced users | EdgeSuite everyday + advanced fallback | Core ON |
| Purchase Invoice creation | Guided `Record Purchase`; native list remains `DocType: Purchase Invoice` | Guided Create / Professional Purchasing | Guided draft creation incorporated active | `KEEP_GUIDED` | Native Purchase Invoice | Mixed | Core ON |
| Purchase Register | `Page: purchase-register` | Same | B4B12 read scope hardened | `KEEP_PAGE` | ERPNext detailed reports where required | EdgeSuite everyday/accounts | Core ON/minimum reporting candidate |
| Purchase Orders | Native DocType plus Professional Purchasing | `professional-purchasing` | Current Page supports bounded PO-oriented workflow; full form still advanced authority | `KEEP_GUIDED` for supported operations; retain native advanced | Native Purchase Order | Mixed | Core/conditional by workflow |
| Purchase Receipts | Native DocType plus Professional Purchasing guided draft | `professional-purchasing` | Saved-draft guided path preserved; advanced completion may remain native where required | `KEEP_GUIDED` for supported operations; retain native advanced | Native Purchase Receipt | Mixed | Core ON for stock buying |
| RFQ / Supplier Quotation / Quality / Landed Cost advanced paths | Professional Purchasing exposes only bounded supported controls; native forms/reports remain advanced | `professional-purchasing` | B1/B2 explicitly bounded; Landed Cost hidden for EdgeSuite-only because it requires native completion | `ADVANCED_ONLY` unless a safe guided path already exists | Native ERPNext | Advanced native | Not required for lean MVP unless client needs |
| Procurement Tracker | Native ERPNext Query Report handoff where unrestricted company scope permits | No RetailEdge dataset clone by design | B4B23 hardened; ERPNext report remains sole source | `KEEP_NATIVE` | Same | Advanced/unrestricted only | MVP conditional |

## Stock

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Product / Item master | `DocType: Item` plus guided New Product Quick Entry | Quick Entry in Create | Restricted Quick Entry contract active; full Item remains ERPNext authority | `KEEP_GUIDED` for simple creation; native advanced for full master | Native Item | Mixed | Core ON |
| Warehouse / stock locations | `DocType: Warehouse` | No full RetailEdge replacement proven | Native ERPNext stock master | `KEEP_NATIVE` | Same | Stock/admin | Core ON/setup |
| Stock Traceability | `Page: stock-traceability-control` | Same | Current Page | `KEEP_PAGE` | Batch/Serial masters | EdgeSuite stock | MVP conditional |
| Batch / Serial records | Native DocTypes | Traceability Page is operational overview, not full master replacement | Keep ERPNext records authoritative | `KEEP_NATIVE` | Same | Stock/advanced | MVP conditional |
| Stock Movement History | `Report: RetailEdge Stock Movement History` | `Page: stock-movement-history` exists | **Explicit parity gate remains incomplete**; prior contract says keep Query Report until parity/export/mobile/browser QA | `DEFER_PARITY` — do not promote in B2/B3 without completing gate | Current Query Report remains primary | Mixed | Core report via current Query Report |
| Stock Position | `Page: stock-position` | Same | B4A hardened | `KEEP_PAGE` | Stock Balance/ledger reports for detail | EdgeSuite everyday | Core ON/minimum reporting candidate |
| Inventory Intelligence | `Page: inventory-intelligence` | Same | Inherits hardened stock dataset | `KEEP_PAGE` | Detailed ERPNext reports | EdgeSuite manager/stock | MVP conditional |
| Transfer Opportunities | `Page: inventory-transfer-opportunities` | Same | Current Page; no route defect identified | `KEEP_PAGE` | Guided Stock Transfer / Stock Entry | EdgeSuite stock | MVP conditional |
| Inventory Ageing | `Page: inventory-ageing` | Same | Current Page | `KEEP_PAGE` | Detailed Stock Ageing native Report | EdgeSuite manager/stock | MVP conditional |
| Stock & Accounting Integrity | `Page: stock-accounting-integrity` | Same | Role gated; reconciled E16 capability | `KEEP_PAGE` | Native ledgers for drill-down | Role-gated advanced control | MVP conditional/admin |
| Stock Balance | Native `Report: Stock Balance` | Stock Position Page available but not a semantic replacement for all native details | ERPNext report remains stock truth | `KEEP_NATIVE` | Same | Stock/accounts | Core ON/detail |
| Stock Transfer | Guided `Transfer Stock`; base/native `DocType: Stock Entry` remains | Guided Create | B3 frozen contract: server revalidates Company/Branch/Warehouses; single/multi/zero scope semantics protected | `KEEP_GUIDED` | Native Stock Entry draft for authorised advanced users | EdgeSuite everyday + advanced fallback | Core ON |
| Stock Count / Adjustment | Guided `Stock Adjustment`; native `Stock Reconciliation` remains | Guided Create | Draft-safe path incorporated active | `KEEP_GUIDED` | Native Stock Reconciliation | Mixed | Core ON |
| Reorder Requests | `DocType: Material Request` | No proven RetailEdge replacement | Native ERPNext workflow | `KEEP_NATIVE` | Same | Stock/purchasing | MVP conditional |
| Stock Ledger / Projected Stock / detailed Stock Ageing | Native Reports | No replacement required | ERPNext detailed truth | `KEEP_NATIVE` | Same | Stock/accounts | Core detail / conditional |

## Assets

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Asset overview | `Page: assets-control` | Same | Current Page | `KEEP_PAGE` | Native Asset masters | EdgeSuite/manager | MVP conditional |
| Fixed Assets / Asset Categories | Native DocTypes | Overview exists but does not replace ERPNext lifecycle | `KEEP_NATIVE` | Same | Same | Advanced/accounts | Feature-off capable for lean retail MVP |

## Money / banking / payments

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cash Movement | `Page: cash-movement` | Same | B4B11 hardened | `KEEP_PAGE` | GL/Payment Entry detail | EdgeSuite accounts/manager | Core ON/minimum reporting candidate |
| Cash Flow Outlook | `Page: cash-flow-outlook` | Same | Role-gated management view; B4B14/B15 consumers hardened | `KEEP_PAGE` | Native AR/AP/GL detail | Role-gated | MVP conditional |
| Payment Management | `Page: payment-management` inserted before native Payment Entry | Same | Current promotion; B4B26 deferred until after RIR baseline | `KEEP_PAGE`; do not start B4B26 during RIR2B1–D | Native Payment Entry / Payment Reconciliation for authorised advanced users | Mixed | Core ON if customer advances/reconciliation required |
| Customer Advance Register | `Report: RetailEdge Customer Advance Register` inserted by master experience | No Page replacement required | B4B25 hardened | `KEEP_NATIVE` RetailEdge report | Payment Entry / reconciliation drill-down | Accounts/manager | MVP conditional |
| Receive Customer Payment | Guided Create | Payment Management may be relevant downstream | Guided Payment Entry creation/allocation semantics preserved | `KEEP_GUIDED` | Native Payment Entry | EdgeSuite everyday + advanced fallback | Core ON |
| Pay Supplier | Guided Create | Payment Management/native ERPNext downstream | Guided Payment Entry semantics preserved | `KEEP_GUIDED` | Native Payment Entry | EdgeSuite everyday + advanced fallback | Core ON |
| Deposit Cash | Guided Create when cashier context permits | Same Create flow | Custody/context gate preserved | `KEEP_GUIDED` | Native Payment Entry advanced | Cashier/finance | Core ON where cash is used |
| Cash / Bank Transfer | Guided Create, finance-role restricted | Same | ERPNext internal-transfer draft remains authority | `KEEP_GUIDED` | Native Payment Entry | Finance roles | Core ON |
| Payments list | `DocType: Payment Entry` remains in base and fallback | `payment-management` exists but is not a full generic Payment Entry replacement | Keep native document truth | `KEEP_NATIVE` as advanced/detail route alongside Page | Same | Advanced/native | Core support route |
| Payment Reconciliation | `DocType: Payment Reconciliation` | Payment Management orchestrates only bounded scenarios | ERPNext reconciliation remains authority | `ADVANCED_ONLY` unless launched through supported Payment Management action | Same | Accounts/native | Core support route |
| Subscriptions / Subscription Plans | Native DocTypes | No RetailEdge replacement proven | Unrelated to core lean retail launch unless client uses subscriptions | `KEEP_NATIVE` | Same | Advanced | MVP conditional/off capable |
| Bank Transactions | `DocType: Bank Transaction` | Banking workspace/pages coexist | Native ERPNext bank transaction remains source truth | `KEEP_NATIVE` for records/detail | Same | Accounts/native | Core ON for banking |
| Import Bank Statement | `DocType: RetailEdge Payment Statement Import` | No replacement required by current matrix | RetailEdge native import DocType | `KEEP_NATIVE` | Same | Banking operator | Core ON if statement import used |
| **Bank Matching** | **Business Hub base: `Report: RetailEdge Bank Transaction Matching`; native fallback workspace: same Report** | **`Page: bank-matching-reconciliation`** | Full current EdgeSuite Page exists; RIR1 confirmed current wrong route. Page roles include Accounts Manager/User and RetailEdge Manager/Branch Manager. Final browser/access verification still required in B2. | **`PROMOTE_B2` -> `Page: bank-matching-reconciliation` in both primary and compact fallback route sources** | Keep legacy Query Report only as an advanced/comparison fallback if still useful; do not delete it | EdgeSuite everyday for permitted banking roles; native report advanced | Core ON if bank matching enabled |
| Banking Setup & Readiness | Not currently a normal Business Hub/fallback item | `Page: banking-readiness` | Page exists and is role-scoped; discoverability not yet deliberately composed | `REVIEW_B3` for a bounded setup/readiness entry; **do not** replace Bank Account or statement setup blindly | Bank Account / mapping native setup | Accounts/manager | MVP conditional but useful for deployment readiness |
| Bank Match Review records | `DocType: RetailEdge Bank Transaction Match` in Review & Approvals | Bank Matching Page may link to review context | Existing banking invariant must remain intact | `KEEP_NATIVE` review record/detail; no route-engine rewrite | Same | Reviewer/accounts | Core conditional with Bank Matching |

### Banking invariant that route work must preserve

`selected report row candidate == batch job locked candidate == Bank Match Review candidate == confirmation candidate`

RIR2B2 changes only navigation. It must not alter discovery, ranking, locking, confirmation or reconciliation execution.

## Expenses

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Expense Register | `Page: expense-register` | Same | B4B7 hardened | `KEEP_PAGE` | Source Cashier Expense records | EdgeSuite everyday/accounts | Core ON/minimum reporting candidate |
| Record Cashier Expense | Guided Create + `DocType: RetailEdge Cashier Expense` | Guided Create | Controlled guided path incorporated active | `KEEP_GUIDED` | Native record/detail for authorised users | Cashier/manager | Core ON |
| Expense Categories | Base native DocType; effective Setup consolidation removes managed setup DocType from Setup group when Setup Page is available | `Page: retailedge-setup` | Current setup architecture supersedes old document-workspace design | `KEEP_PAGE` through Setup for normal configuration | Native DocType advanced | Admin | Core setup |

## Customers

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Customer master | `DocType: Customer` plus guided New Customer Quick Entry | Quick Entry | Permission-aware Quick Entry incorporated active | `KEEP_GUIDED` simple creation; native list/form remains master authority | Native Customer | Mixed | Core ON |
| Customer Receivables | `Page: customer-receivables` | Same | B4B14 hardened | `KEEP_PAGE` | `Report: Accounts Receivable` detail | EdgeSuite accounts/manager | Core ON/minimum reporting candidate |
| Customer & Sales Intelligence | `Page: customer-sales-intelligence` | Same | Current consumer inherits scoped sales/receivables authorities | `KEEP_PAGE` | Sales Invoice/AR drill-down | EdgeSuite manager | MVP conditional |
| Customer 360 | `Page: customer-360` | Same | Current scoped consumer | `KEEP_PAGE` | Native Customer and transactions | EdgeSuite operations/manager | MVP conditional |
| Retention & Opportunities | `Page: customer-opportunity-intelligence` | Same | Current Page | `KEEP_PAGE` | Native sales docs | EdgeSuite sales/manager | MVP conditional |
| Detailed Accounts Receivable | Native ERPNext Report | Customer Receivables Page exists as operational summary | Native detailed report remains authority | `KEEP_NATIVE` detail | Same | Accounts/advanced | Core detail |

## Service & Warranty

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Service & Warranty overview | `Page: service-warranty-control` | Same | Current Page | `KEEP_PAGE` | Native service docs | EdgeSuite/manager | MVP conditional/off capable |
| Warranty Claims | Native DocType; quick action is `native_fallback` only | No fully guided RetailEdge creation contract | EdgeSuite-only users intentionally do not receive native-only quick action | `ADVANCED_ONLY` until supported guided flow exists | Native Warranty Claim | Native Desk users only | Not required for base MVP unless client needs |
| Maintenance Schedules / Visits | Native DocTypes | No replacement proven | Native ERPNext workflow | `KEEP_NATIVE` | Same | Advanced | MVP conditional/off capable |

## Suppliers & Payables

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Supplier master | `DocType: Supplier` plus guided New Supplier Quick Entry | Quick Entry | Permission-aware Quick Entry active | `KEEP_GUIDED` simple creation; native list/form remains master authority | Native Supplier | Mixed | Core ON |
| Supplier Payables | `Page: supplier-payables` | Same | B4B12 Purchase Reporting authority hardened | `KEEP_PAGE` | `Report: Accounts Payable` detail | EdgeSuite accounts/purchasing | Core ON/minimum reporting candidate |
| Payment Orders | Native DocType | No RetailEdge replacement proven | Native ERPNext workflow | `KEEP_NATIVE` | Same | Accounts/advanced | MVP conditional |
| Detailed Accounts Payable | Native ERPNext Report | Supplier Payables operational Page exists | Detailed native report remains authority | `KEEP_NATIVE` detail | Same | Accounts/advanced | Core detail |

## Insights / dashboards

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sales by Item | `Page: sales-by-item` | Same | B4B13 scope hardened | `KEEP_PAGE` | Native Sales Invoice detail | EdgeSuite manager/sales | Minimum report candidate / Core ON |
| Sales Forecast | `Page: sales-forecast` | Same | Current Page | `KEEP_PAGE` | Native source docs | Manager | MVP conditional |
| Forecasting & Planning | `Page: forecasting-planning` | Same | Current Page | `KEEP_PAGE` | Planning Scenario DocType | Manager | MVP conditional/off capable |
| Planning Scenarios | Native RetailEdge DocType | Planning Page orchestrates scenarios | Keep persisted scenario record native | `KEEP_NATIVE` | Same | Manager/advanced | MVP conditional |
| Basket & Product Affinity | `Page: basket-affinity` | Same | Current advanced insight | `KEEP_PAGE` | Transaction drill-down | Manager | MVP conditional/off capable |
| Discount & Sales Quality | `Page: sales-quality-intelligence` | Same | Current advanced insight | `KEEP_PAGE` | Sales document drill-down | Manager | MVP conditional/off capable |
| Sales Invoice Register | `Page: sales-invoice-register` | Same | B4B13 scope hardened | `KEEP_PAGE` | Native Sales Invoice detail | Sales/accounts | Core/minimum reporting candidate |
| Salesperson Performance | `Page: salesperson-performance-dashboard` | Same | Current dashboard; B4B6 scope hardened | `KEEP_PAGE` | Native sales/team reports | Manager | MVP conditional |
| Branch Performance | `Page: branch-performance-dashboard` | Same | B4B2 scope hardened; intended primary dashboard | `KEEP_PAGE` | Existing detailed Query Reports/drill-down only | Manager/branch manager | Core ON when branch KPI relevant |
| Inventory + Profitability | `Page: inventory-profitability` | Same | Current insight; management accounting visibility restrictions must remain | `KEEP_PAGE` | Native stock/accounting detail | Manager/accounts | MVP conditional/off capable |

## Review & Approvals

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Business Control Centre | `Page: business-control-center` | Same | Current role-gated composite control | `KEEP_PAGE` | Native source documents | Manager/control roles | MVP conditional |
| Action Centre | `Page: action-center` | Same | B4B18–B4B20 hardened | `KEEP_PAGE` | Action Follow Up records for permitted readers | Manager/control roles | MVP conditional |
| Supplier Document Review | `Page: supplier-document-review` | Same | Current role-gated Page | `KEEP_PAGE` | Native buying docs | Purchasing/accounts | MVP conditional |
| Bank Match Reviews | Native RetailEdge Bank Transaction Match DocType | Bank Matching Page exists for operational matching, not record replacement | Keep review record authority | `KEEP_NATIVE` | Same | Reviewer/accounts | Conditional with Bank Matching |
| Daily Sales Audit | **Effective Business Hub: `Page: daily-sales-audit`**; base/fallback still native `RetailEdge Daily Sales Audit` | Same | Browser-approved R4 promotion; B4B5/B9 hardened | `KEEP_PAGE` in Business Hub | Native audit record in compact/advanced context | EdgeSuite everyday control + native advanced | Core/conditional |
| Cashier Expense Review | **Effective Business Hub: `Page: expense-review`**; base/fallback uses `Report: RetailEdge Cashier Expense Review` | Same | Browser-approved R4 promotion; B4B10 consolidated scope | `KEEP_PAGE` in Business Hub | Native Query Report remains detail/fallback | EdgeSuite control + advanced report | Core/conditional |
| Cash Shift Verification | **Effective Business Hub: `Page: cash-shift-verification`**; base/fallback uses legacy Report | Same | Browser-approved R4 promotion; B4B8 hardened | `KEEP_PAGE` in Business Hub | Legacy Report detail/fallback | EdgeSuite control + advanced report | Core/conditional |
| Invoice Payment Audit | Native RetailEdge Report | No Page replacement proven | Existing report | `KEEP_NATIVE` | Same | Reviewer | MVP conditional |
| POS Closing Variance vs Expenses | Native Report | No replacement proven | Existing report | `KEEP_NATIVE` | Same | Manager | MVP conditional |
| Unmatched Bank Transactions / Payments | Native RetailEdge Reports | Bank Matching Page is broader operational surface but these reports remain focused diagnostics | Do not collapse semantics during route recovery | `KEEP_NATIVE` diagnostics | Same | Banking/reviewer | Conditional with bank matching |
| Reconciliation Readiness / Handoff | Native RetailEdge Reports | Banking Readiness Page is a different setup/readiness concern | Existing controls remain separate | `KEEP_NATIVE` | Same | Reviewer/accounts | Conditional |
| Daily Sales Audit Register | Native RetailEdge Report | Daily Sales Audit Page is operational surface, register remains detail | B4B9 hardened | `KEEP_NATIVE` detail | Same | Manager/accounts | Conditional |

## Accounting

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| General Ledger | Native ERPNext Report | No RetailEdge replacement required | ERPNext accounting truth | `KEEP_NATIVE` | Same | Accounts roles | Core detail/admin |
| Trial Balance | Native ERPNext Report | No replacement required | ERPNext accounting truth | `KEEP_NATIVE` | Same | Accounts roles | Core detail/admin |
| Profit & Loss | Native ERPNext Report | Management pages may summarize but do not replace ledger report | ERPNext accounting truth | `KEEP_NATIVE` | Same | Accounts roles | Core financial reporting/detail |
| Balance Sheet | Native ERPNext Report | Same principle | ERPNext accounting truth | `KEEP_NATIVE` | Same | Accounts roles | Core financial reporting/detail |
| Cash Flow Statement | Native ERPNext Report | Cash Movement/Outlook Pages are operational, not replacement for statutory/native report | ERPNext accounting truth | `KEEP_NATIVE` | Same | Accounts roles | Core detail/conditional |
| Budgeting & Cost Control | `Page: budget-control` | Same | Current Page | `KEEP_PAGE` | Budget DocType / Budget Variance report | Accounts/manager | MVP conditional |
| Budgets / Budget Variance | Native DocType/Report | Budget Control Page exists | Keep native budget truth | `KEEP_NATIVE` | Same | Accounts/advanced | MVP conditional |
| Cost Centers | Native DocType | No replacement required | Accounting master | `ADVANCED_ONLY` | Same | Accounts/admin | Required setup where used |
| Journal Entries | Native DocType | No guided everyday replacement by design | High-risk accounting operation; native ERPNext must remain authority | `ADVANCED_ONLY` | Same | Accounts Manager/System Manager | Not everyday MVP surface |

## Projects — dynamically inserted when available

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Project Operations | `Page: project-operations` when permitted | Same | Current dynamic promotion; B4B22 only hardened branch option search, not full project redesign | `KEEP_PAGE` | Native Project | Project roles | `MVP_CONDITIONAL`; likely OFF for lean first client unless needed |
| Project Portfolio | `Report: RetailEdge Project Portfolio` | No Page replacement required | Current dynamic report | `KEEP_NATIVE` report | Same | Project/manager | MVP conditional/off capable |
| Project Financial Control | `Report: RetailEdge Project Financial Control` | No Page replacement required | Current dynamic report | `KEEP_NATIVE` report | Same | Manager/accounts | MVP conditional/off capable |
| Project master | Native `DocType: Project` when readable | Project Operations Page exists but does not replace full Project record | ERPNext Project remains source | `KEEP_NATIVE` | Same | Advanced/project | MVP conditional/off capable |

## Setup / administration

| Business operation | Current target | Available RetailEdge Page | Parity / QA state | Everyday target decision | Native fallback | Access mode | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RetailEdge Setup | **Effective Business Hub: `Page: retailedge-setup`** | Same | Current setup consolidation architecture | `KEEP_PAGE` | Managed DocTypes remain advanced records if needed | System Manager | Core deployment/admin |
| RetailEdge Settings | Removed from effective Business Hub Setup group when Setup Page is available; base/fallback still native DocType | `retailedge-setup` | Superseded direct everyday setup route | `KEEP_PAGE` via Setup | Native Settings advanced | System Manager | Core deployment/admin |
| Branch Setup | Managed by Setup Page in effective Business Hub; base/fallback has `RetailEdge Branch Profile`; dedicated `branch-setup` Page also exists | `retailedge-setup`, `branch-setup` | Current consolidation intentionally removes managed DocType from primary Business Hub | `KEEP_PAGE` via consolidated Setup; no new promotion during B1 | Branch Profile native advanced | System Manager | Core deployment/admin |
| Branch Assignments | Dedicated Page exists but is not a base navigation item in `edgesuite_ui.py` | `branch-assignments` | Branch assignment model is security-critical; discoverability belongs to controlled setup, not broad navigation | `REVIEW_B3` only for Setup integration if not already reachable inside Setup | Native records/admin tooling | System Manager | Core deployment/admin |
| Expense Categories | Managed by Setup Page | `retailedge-setup` | Current consolidation | `KEEP_PAGE` via Setup | Native DocType advanced | System Manager | Core setup |
| Statement Mapping | Managed by Setup Page | `retailedge-setup` | Current consolidation | `KEEP_PAGE` via Setup | Native DocType advanced | System Manager/accounts | Conditional with banking |
| Bank Accounts | Native DocType remains in effective Setup | Banking Readiness Page exists but is not a full Bank Account replacement | ERPNext Bank Account remains source | `KEEP_NATIVE` | Same | System Manager/accounts | Core banking setup |
| Modes of Payment | Native DocType remains | No replacement needed | ERPNext master | `KEEP_NATIVE` | Same | System Manager/accounts | Core payments setup |

---

# Frozen RIR2B1 promotion decisions

## Confirmed RIR2B2 change

Only one route correction is confirmed strongly enough to enter RIR2B2 immediately after this matrix is frozen green:

**Bank Matching**

- Current primary Business Hub source: `Report: RetailEdge Bank Transaction Matching`
- Current compact native workspace source: `Report: RetailEdge Bank Transaction Matching`
- Current RetailEdge operational Page: `Page: bank-matching-reconciliation`
- B2 target: promote **both route sources** to `Page: bank-matching-reconciliation` for permitted users.
- Preserve the Query Report as an advanced/comparison fallback only if current navigation/access design still needs it; do not delete report code in B2.
- Add route/access regression coverage.
- Do not touch discovery, scoring, batch locking, Bank Match Review, confirmation or reconciliation execution.

## Explicitly not part of RIR2B2

- **Stock Movement History** stays on `Report: RetailEdge Stock Movement History`. Its Page promotion remains blocked by parity/export/mobile/browser QA.
- Do not blanket-replace Sales, Purchase, Stock, Payment, Accounting or setup DocTypes with RetailEdge Pages simply because related Pages exist.
- Do not change Professional Selling/Purchasing business semantics.
- Do not start B4B26.
- Do not redesign Business Hub.
- Do not perform navigation deduplication yet; that is RIR2D after route decisions are frozen.

## RIR2B3 review candidates

These require separate bounded evidence before any promotion/addition:

1. `Page: banking-readiness` — consider controlled discoverability in Money/Setup for permitted Accounts/RetailEdge management roles. It must not replace Bank Account, statement mapping, or import configuration semantics.
2. `Page: branch-assignments` — consider controlled inclusion inside consolidated Setup if normal System Manager onboarding otherwise cannot reach it. Branch Assignment security semantics must remain untouched.
3. Any additional native-to-Page route discovered during local persona QA must be added to this matrix first, with explicit parity evidence, before changing navigation.

No other current native destination is pre-approved for RIR2B3 promotion by this matrix.

# Compact fallback reconciliation observations

The compact native workspace intentionally has fewer capabilities than the Business Hub. It also still carries several older route forms that the effective Business Hub already promotes:

- Daily Sales Audit: native DocType in fallback vs Page in Business Hub.
- Cashier Expense Review: Report in fallback vs Page in Business Hub.
- Cash Shift Verification: Report in fallback vs Page in Business Hub.
- Setup managed DocTypes: direct fallback entries vs consolidated Setup Page in Business Hub.
- Bank Matching: **legacy Report in both**, therefore a genuine route defect rather than an intentional primary/fallback distinction.

RIR2D may later canonicalize accidental duplicate/alias exposure after RIR2B promotions are complete. RIR2B1 does not alter these existing distinctions.

# Access-mode contract

Route availability is always the intersection of:

1. target existence;
2. Frappe Page/DocType/Report permission;
3. RetailEdge role constraints where present;
4. current EdgeSuite interface exposure (`can_use_native_desk`);
5. server-authoritative Company/Branch/other operating scope in the destination backend.

A Page being visible must never grant data access outside the backend scope. Conversely, hiding a native target is not a substitute for backend authorization.

# MVP interpretation

This matrix is **not** the future feature registry. It freezes routing truth before feature-disable work starts.

After the final reconciliation baseline:

- core sales, purchasing, stock, payments, expenses, receivables, payables, cash/bank and minimum reporting remain launch candidates;
- advanced analytics, projects, service/warranty, subscriptions and optional control surfaces may remain reconciled in code but be switched OFF through the later centralized feature registry;
- accounting validation, permissions, branch scope and immutability protections are never feature-disabled.

# RIR2B1 acceptance criteria

RIR2B1 is complete only when:

- this matrix exists on the PR #55 head;
- a source-contract test freezes the key current route facts without implementing B2;
- Bank Matching is recorded as the sole confirmed immediate B2 promotion;
- Stock Movement History is explicitly held on its current Query Report;
- current Business Hub dynamic promotions are represented;
- the compact fallback workspace is represented;
- all PR #55 automated gates are green on the exact final RIR2B1 head;
- PR #55 remains draft/open/unmerged;
- no route, business workflow, accounting, stock, payment or branch-scope behavior has changed.

# Next slice after green freeze

**RIR2B2 — Bank Matching route correction**, limited to promoting the confirmed Bank Matching navigation target to `Page: bank-matching-reconciliation` in the applicable primary/fallback route sources plus focused route/access regression coverage.
