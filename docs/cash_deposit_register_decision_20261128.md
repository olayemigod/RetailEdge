# Cash Deposit Register — engineering decision and acceptance

## Basis

- Authoritative RetailEdge version-16 base: ce11879ebf7374c2a7d69dc91a8ead23a391eb51. Restored-site QA uses Frappe/ERPNext v16 series; exact current app pins must be recorded before combined acceptance.
- ERPNext Payment Entry (Internal Transfer) is the accounting document. Drafts do not post to GL; submitted entries do. See https://docs.frappe.io/erpnext/payment-entry and https://docs.frappe.io/erpnext/banking-in-erpnext.
- Frappe v16 permission-aware get_list and structured aggregate fields: https://docs.frappe.io/framework/user/en/api/database. Do not use unrestricted get_all or a second deposit ledger.
- Shopify POS register-session activity/history and separate staff permissions are useful operational precedents: https://help.shopify.com/en/manual/sell-in-person/shopify-pos/cash-register-management/register-sessions-in-shopify-pos and https://help.shopify.com/en/manual/sell-in-person/shopify-pos/cash-register-management/cash-tracking-reports-by-location. Do not copy a separate drawer ledger or loosen ERPNext authority.
- Existing RetailEdge Payment History provides branch scoping, pagination, status/period filters and native document read checks. Its Page is accounting-role-only; do not widen access to general payment history just to expose deposits.
- Existing Standard Internal Transfer Completion handles review, workflow and submit. Reuse it in the UI rather than posting directly. PR #259 corrects Select-only account handling; PR #260 separates expense reservations from physical till cash. Both remain independent of the register read service.

## First slice

The read-only GET service lists only marked Cash Deposit/Internal Transfer Payment Entries. It intersects native Payment Entry read permission, Company read permission and operational Branch scope. Cashier-only users are scoped to their own cashier attribution; reviewers with appropriate native permissions may view their permitted Branch population. No permission grant, schema change, posting or closing change. Optional filters never widen authority. Totals use the same permission-aware filtered set as the page, grouped by document state and currency; drafts and cancelled records are not posted deposits. No global counts are returned outside that set.

## Remaining UI / completion scope

- EdgeSuite Cash Deposit Register page, navigable from Cash, Bank & Reconciliation and Cashier My Work when permitted. Reuse current shared Link, Dropdown, fuzzy search, Smart Date, table/status, pagination and modal primitives. Verify actual pinned EdgeSuite runtime and Frappe v16.50+ native contracts before adding new primitives; no new primitive is needed for the backend slice.
- Company/Branch/cashier/bank/shift filters must cascade and expose only authorized choices; search and date filters; stale-response protection, dark/light themes.
- Use existing Standard Internal Transfer Completion for permitted draft review and submission, respecting workflow and expected modified value; native Advanced and draft delete only when authorized. Do not auto-submit or mutate existing drafts.
- Verify historical record visibility, native read/field/row permissions, role-exact cashiers without generic Payment Entry Read (deny; no grant), manager, auditor, branch manager and unauthorized personas, cross-company/branch/cashier filter tampering, exact pagination totals, currency separation, and direct GET/POST denial.
- Isolated acceptance fixture: 1 submitted deposit of NGN 2,000, 3 drafts totaling NGN 6,000; submitted GL debit/credit NGN 2,000. Drafts do not reduce custody; only the submitted amount does. Preserve all four test records. Expected till cash NGN 51,000, reservations NGN 25,000, policy availability NGN 26,000, subject to independent receipt/closing reconciliation.
- No Production deployment, merge, hosted migration, permission expansion or cleanup is authorized. UI, integration tests, browser/permission persona tests and exact-head gates remain required before acceptance.
