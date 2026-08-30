# E16 C5A — Native Payment Order Discoverability

## Goal

Expose ERPNext's existing Payment Order workflow inside RetailEdge's governed EdgeSuite navigation so authorised Accounts users can discover and use native payment-order processing without RetailEdge creating a second batch-payment engine.

## Predecessor checkpoint

Start only from the fully green C4A checkpoint:

`7706fe6552b12bc163c5ea3f807a3dbc3633ea56`

Validated exact-head gates:

- RetailEdge Theme Compatibility #161: PASS
- Linters #1911 / #1912: PASS
- CI #1929 / #1930: PASS
- EdgeSuite UI Candidate Compatibility #167 / #168: PASS

Continue only on PR #53 / `agent/competitive-gap-nextgen-20260829`. Do not create a divergent implementation branch or PR.

## Audit result

ERPNext v16 already owns Payment Order:

- standard submittable `Payment Order` DocType;
- native permissions for Accounts User and Accounts Manager;
- imports already initiated submitted Payment Requests or Payment Entries;
- Payment Order submission updates the native payment-order state of its references;
- native Payment Request payment orders can create supplier Journal Entries using ERPNext's own Payment Order workflow.

Therefore RetailEdge must not add:

- a custom payment-run DocType;
- a supplier batch-payment ledger;
- custom Payment Order posting logic;
- browser-generated Journal Entries;
- automatic Payment Entry submission;
- direct GL or Payment Ledger writes.

The current RetailEdge EdgeSuite navigation exposes Supplier Payables and detailed Accounts Payable, but does not expose Payment Order. Because RetailEdge hides/replaces much of the native operational navigation with its governed EdgeSuite shell, discoverability is the genuine gap.

## C5A scope

- Add `Payment Orders` as a native DocType navigation item under `Suppliers & Payables`.
- Target the standard ERPNext `Payment Order` DocType.
- Let the existing RetailEdge navigation resolver verify that the DocType exists and that the current user has native read permission.
- Do not hard-code broader RetailEdge roles that would bypass ERPNext's Accounts User / Accounts Manager permissions.
- Keep Supplier Payables, Accounts Payable and Payment Entry routes unchanged.
- Do not add a new page, dialog, API, mapper, DocType or accounting service.
- Do not present Payment Order as direct unpaid-invoice batch payment; its source/reference semantics remain exactly those implemented by ERPNext.

## EdgeSuite UI policy

This slice changes only the data feeding the existing EdgeSuite navigation. The governed `window.EdgeSuiteUI` Business Hub/shell remains the frontend runtime.

- no new operational frontend framework;
- no `window.EdgeUI`;
- no `frappe.ui.Dialog` or `frappe.prompt` added by RetailEdge;
- native ERPNext Payment Order forms remain the authoritative workflow surface after navigation.

ERPNext's own native form implementation may use Frappe form/dialog APIs; C5A does not copy or wrap those APIs into RetailEdge frontend code.

## Safety

RetailEdge performs no Payment Order write in C5A. Native ERPNext permissions and document lifecycle remain authoritative.

Do not:

- submit or cancel Payment Orders from RetailEdge code;
- create Journal Entry from RetailEdge code;
- mutate Payment Request or Payment Entry payment-order status;
- add `ignore_permissions=True`;
- add manual `frappe.db.commit()`;
- add direct GL Entry or Payment Ledger Entry writes.

## Tests required

- navigation contract contains `Payment Orders` → `Payment Order` under `Suppliers & Payables`;
- Payment Order remains a `DocType` target so `_can_open_target` applies native read permission checks;
- no custom Payment Order backend service or page is introduced;
- existing Supplier Payables / Accounts Payable / Payments navigation remains present;
- no new legacy RetailEdge frontend dialog/prompt implementation is introduced;
- exact-head Theme, Linters, clean Frappe v16 CI/full RetailEdge tests and governed EdgeSuite UI candidate compatibility pass.

## Recovery rule

If C5A is interrupted, resume from this contract and the latest PR #53 head. Do not rebuild prior green checkpoints and do not begin another E16 slice until the exact C5A head is green.
