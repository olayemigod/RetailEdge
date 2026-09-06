# E16 Supplier Payment Operations — bounded implementation contract

## Goal

Close the contextual action gap between RetailEdge Supplier Payables and the already implemented ERPNext-native supplier payment draft flow. Users reviewing what is owed should be able to start a correctly scoped supplier Payment Entry draft from the payables worklist without re-entering the Supplier and Purchase Invoice.

This is an orchestration/usability slice. ERPNext remains the accounting source of truth.

## Predecessor checkpoint

Start only from the fully green Professional Purchasing C3A checkpoint:

`ea00803aa350e3bb8e6d76387cd048b4319d2491`

C3A exact-head validation passed Theme, Linters, clean Frappe v16 CI/full RetailEdge tests, and governed EdgeSuite UI candidate compatibility.

Continue only on PR #53 / `agent/competitive-gap-nextgen-20260829`. Do not create a divergent implementation branch or PR.

## Audit result before C4A

Do not implement another Purchase Order/Purchase Receipt billing or return engine:

- ERPNext v16 Purchase Order already maps remaining unbilled quantities to Purchase Invoice.
- ERPNext v16 Purchase Receipt already maps remaining billable receipt quantities to Purchase Invoice.
- native Purchase Receipt already owns Purchase Return, rejected-warehouse return, Debit Note and Landed Cost Voucher flows.
- RetailEdge Simple Purchase Invoice remains the independent-entry draft path and must not be converted into a competing PO/receipt mapper.

Do not implement another generic supplier-payment composer:

- `retailedge.guided_payment` already supports the `pay-supplier` intent over standard ERPNext Payment Entry.
- the existing `SimplePaymentDialog.vue` already supports both customer receipt and supplier payment intents through EdgeSuite UI.
- Business Hub already exposes `Pay Supplier` as a permission-aware quick action.

The remaining gap is contextual action from the Supplier Payables worklist.

## C4A — Supplier Payables → draft Payment Entry handoff

### Business outcome

An Accounts/Purchase user can review outstanding Purchase Invoices in Supplier Payables and choose **Pay Supplier** on a payable row. RetailEdge opens the existing EdgeSuite `SimplePaymentDialog` already scoped to `pay-supplier`, prefilled from the selected authoritative Purchase Invoice. The user reviews payment mode, amount and allocation, then saves only a draft ERPNext Payment Entry.

### Scope

- Extend the existing EdgeSuite `Supplier Payables` report; do not create a new payables page.
- Add a bounded row-level payment action only for `supplier_payables` rows.
- Reuse `SimplePaymentDialog.vue`; do not create another supplier payment form or modal.
- Extend the reusable dialog only as needed to accept safe optional initial context/prefill.
- Prefill only identifiers that are already present in the permission-scoped Supplier Payables row: Supplier and Purchase Invoice. Company/Branch must remain server-validated/resolved by existing guided-payment APIs.
- When a Purchase Invoice is prefilled, reload its current authoritative outstanding amount through `get_simple_payment_reference_details`; never trust the displayed report balance as the write amount.
- Default allocation may use the freshly reloaded outstanding amount, but the user remains able to reduce the payment/allocation before saving.
- Reuse `create_simple_payment_draft(intent='pay-supplier')` unchanged where possible.
- Result remains a standard ERPNext Payment Entry with `payment_type = Pay`, `party_type = Supplier`, Purchase Invoice references, and current-user permissions.
- Payment Entry must remain draft. The user reviews/submits through the native ERPNext Payment Entry form.
- Refresh Supplier Payables after a draft is created only to keep UI state current; do not claim the outstanding amount has changed because a draft Payment Entry is not posted.
- Preserve native Payment Entry, Supplier Payables and Accounts Payable routes.

### EdgeSuite UI policy — hard gate

- Use only `window.EdgeSuiteUI` and existing shared EdgeSuite components.
- Reuse the existing `EdgeReportShell` Supplier Payables surface and `SimplePaymentDialog`/`EdgeModal`.
- No `window.EdgeUI`.
- No `frappe.ui.Dialog`.
- No `frappe.prompt`.
- No `frappe.msgprint` or `frappe.show_alert` for the new workflow.
- Native ERPNext forms/reports are permitted as authoritative completion/fallback surfaces.

### Backend/accounting safety

Do not add a new payment ledger, supplier wallet, payables ledger, allocation DocType or payment-run persistence model.

Do not:

- auto-submit Payment Entry;
- mutate submitted Purchase Invoice fields or `outstanding_amount`;
- write GL Entry directly;
- write Payment Ledger Entry directly;
- manually commit the database;
- bypass ERPNext party/account/mode-of-payment/reference validation;
- infer cross-company or cross-branch allocations in the browser;
- silently support multi-currency in the guided path.

Multi-currency and other unsupported accounting cases must remain on the full ERPNext Payment Entry workflow.

### Explicitly out of scope

- multi-supplier batch payment runs;
- automatic bank-file generation;
- payment approvals/workflow replacement;
- automatic Payment Entry submission;
- supplier advances/prepayments beyond existing ERPNext/native capabilities;
- payment scheduling or recurring payments;
- purchase invoice creation, returns, Debit Notes or Landed Cost Voucher orchestration;
- custom three-way matching.

### Tests required

- existing `pay-supplier` backend contract remains unchanged and green;
- Supplier Payables adds contextual Pay Supplier only on the supplier-payables report, not Purchase Register;
- clicking a payable row action opens the existing `SimplePaymentDialog` with `intent='pay-supplier'`;
- safe optional prefill does not bypass fresh server reference lookup;
- Supplier/Purchase Invoice changes clear or refresh stale allocation data;
- draft save still delegates to `create_simple_payment_draft`;
- no auto-submit or Purchase Invoice mutation is introduced;
- company/branch/supplier/invoice permissions continue to be enforced server-side;
- unsupported multi-currency remains native-form fallback;
- frontend contract requires `window.EdgeSuiteUI` and rejects legacy Frappe dialog/prompt/message APIs in the changed workflow;
- full RetailEdge regression suite, Theme, Linters, clean Frappe v16 CI and governed EdgeSuite UI candidate compatibility all pass at the exact final head.

## Recovery rule

If C4A is interrupted, resume from this contract and the latest commit on PR #53. Do not rebuild C1-C3A and do not begin a later E16 slice until the exact C4A head is green.
