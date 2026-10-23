# RetailEdge MVP-C2 — Physical / merchant acceptance

Date: 2026-10-20

## Purpose

This is the bounded release-acceptance slice immediately after MVP-C1 User Readiness. It does not add product features or reopen completed selling, purchasing, stock, banking, reporting, cashier, workflow, or user-readiness scope.

Authoritative starting point:

- RetailEdge `version-16`: `00e85a98c4d15ebab003af784326d04bdf51f51e`
- This is the merge commit for PR #236.
- Frappe: `16.52.0`
- ERPNext: `16.51.1`
- EdgeSuite UI: `1.1.0` at `d50920b005da8dcf1bd1e35c1c88be8afedecfbf`
- Python: `3.14`
- Node: `24`

`platform-baseline.json` remains `candidate` with `manual_retail_local_qa_required = true` until this acceptance is actually completed. Do not promote the manifest merely because this checklist exists.

## MVP-C2 policy decisions

### 1. No feature expansion

MVP-C1 is complete through PR #236. MVP-C2 is release evidence only. A defect discovered during acceptance may be fixed in a bounded corrective PR, but no unrelated feature work is permitted in this slice.

### 2. Browser USB support boundary for RetailEdge 1.0

RetailEdge 1.0 does **not** claim Browser WebUSB printing as production-proven hardware support.

Supported 1.0 printing promise:

- normal system printing / Print Document;
- configured Serial / Bluetooth direct receipt printing where the shared EdgeSuite printing runtime and target device support it;
- governed receipt formats already covered by automated and existing hardware evidence.

WebUSB remains an optional / preview hardware-dependent path until physical device acceptance is completed on representative supported hardware.

Reason:

- the existing RetailEdge Browser USB reconciliation record explicitly says prior Bluetooth/Serial evidence does not accept Browser USB and still requires physical device validation;
- WebUSB remains an experimental, limited-availability browser API and requires a secure context;
- Windows driver ownership can prevent the browser from claiming a USB printer interface, so a normal system-print fallback remains mandatory.

References:

- `docs/browser-usb-v1652-reconciliation.md`
- https://developer.mozilla.org/en-US/docs/Web/API/WebUSB_API

This policy does not remove the existing WebUSB code path. It defines the 1.0 support claim so an unaccepted hardware path cannot silently become a release blocker or be advertised as universally production-proven.

## Required preflight on `retail.local`

Record evidence before beginning the merchant journey.

1. Confirm the deployed RetailEdge commit and record it.
2. Confirm Frappe, ERPNext, EdgeSuite UI, POSNext and ProcessEdge POSNext Override installed versions/commits.
3. Confirm the platform pins still match `platform-baseline.json` or record the exact approved deviation.
4. Run migration for the deployed candidate.
5. Build RetailEdge and governed EdgeSuite UI assets.
6. Clear site/server cache and hard-refresh the browser.
7. Confirm Business Hub, Professional Selling, Professional Purchasing, Branch Assignment/User Readiness, stock, cashier and reporting surfaces load without asset/runtime errors.
8. Confirm the candidate has already passed its required automated exact-head gates before using manual QA as release evidence.

Any deployed-code drift from the candidate under test invalidates the acceptance record until the exact deployed SHA is identified and the affected gates are rerun.

## Merchant fixture

Use one small but realistic merchant on `retail.local`.

### Administration / setup

Verify or configure:

- Company;
- Branch;
- Warehouse;
- POS Profile where applicable;
- Mode of Payment including cash and one non-cash mode;
- selling Price List;
- RetailEdge setup;
- one manager;
- one cashier;
- one sales user;
- one stock / purchase user;
- one accounts user.

For operational users, verify the MVP-C1 readiness contract before transacting:

- intended RetailEdge capability;
- Company assignment;
- Branch assignment;
- primary operating context;
- POS context where required;
- Ready status for the intended journey;
- an intentionally incomplete user remains fail-closed with meaningful setup guidance and no silent Branch assignment.

## Required start-to-close merchant journey

Perform the journey through the normal EdgeSuite-first surfaces unless the step is explicitly an Advanced ERPNext boundary.

### A. Opening and sales

1. Open the cashier/POS shift.
2. Create a normal sale.
3. Complete one cash payment.
4. Complete one non-cash or mixed payment where configured.
5. Confirm edited item price, tax and discount totals are reflected correctly in the invoice total.
6. Confirm Branch, cashier/user and transaction context are correct on the order/receipt surfaces.
7. Print at least one receipt using a supported 1.0 path:
   - system printing, or
   - already-supported Serial / Bluetooth direct printing.
8. Confirm 80mm or configured receipt content is readable and does not mutate the submitted transaction.

### B. Cash accountability

9. Record a cashier expense.
10. Record a cash deposit/removal using the governed existing workflow where configured.
11. Verify expected cash incorporates the configured expense/deposit behavior correctly.

### C. Returns and customer money

12. Create a return / credit note against the original transaction using the governed ERPNext-backed return path.
13. Record a customer payment against an eligible receivable.
14. Confirm balances and status change without duplicate payment/accounting entries.

### D. Stock

15. Perform a stock count / adjustment through the existing Stock Reconciliation-backed flow.
16. Perform a stock transfer between governed warehouses/branches as configured.
17. Verify source/destination quantities and Branch scope.
18. Confirm ordinary users cannot cross Company/Branch scope through UI or direct saved context.

### E. Purchasing and supplier money

19. Create the normal purchase journey required by the merchant fixture.
20. Complete receipt and Purchase Invoice progression through the governed existing owner/workflow.
21. Record a supplier payment against an eligible payable.
22. Confirm stock/accounting effects are produced by ERPNext documents, not parallel RetailEdge truth.

### F. Closing and reconciliation

23. Close the cashier/POS shift.
24. Enter the actual closing cash.
25. Open Shift Reconciliation.
26. Confirm opening cash, cash sales, cashier expenses, deposits and counted closing cash reconcile to the expected variance.
27. Review shortage/overage behavior if the fixture deliberately includes a variance.
28. Confirm no duplicate posting is created by reopening/revisiting read surfaces.

### G. Management review

29. Review Business Hub for the same Company/Branch/period.
30. Review at minimum:
    - Sales Register / sales view;
    - Branch Performance;
    - Stock Position;
    - Stock Movement;
    - expenses/cashier register;
    - receivables;
    - payables;
    - banking/reconciliation where fixture data exists.
31. Confirm totals reconcile to the transactions created during this merchant journey.
32. Confirm Company -> Branch filters/cascades remain valid and no stale Branch selection survives an invalid parent change.

## Permission/persona checks during the journey

At minimum confirm:

- Manager can perform intended management/review actions.
- Cashier can perform the cashier journey but cannot gain unrelated accounting/stock administration.
- Sales user can perform permitted selling actions only within assigned scope.
- Stock/purchase user can perform permitted stock/purchase actions only within assigned scope.
- Accounts user can perform permitted payment/accounting review without acquiring operational Branch authority beyond configured permissions.
- An intentionally incomplete user remains blocked from governed operational APIs and receives repair guidance.
- An unauthorized persona cannot reveal an `Advanced` action merely because the EdgeSuite page is visible.

A UI-hidden action without server-side denial is a failure.

## USB preview validation — separate from 1.0 release acceptance

When representative USB hardware is available, record this separately. Failure or non-execution of this preview matrix does not fail MVP-C2 under the 1.0 support policy above.

- secure browser context;
- explicit USB profile/device binding;
- device claim succeeds when the browser is allowed to own the interface;
- safe claim failure when the Windows driver owns the interface;
- test print;
- receipt text/readability;
- cutter, barcode and encoding where hardware permits;
- normal Windows/system printing fallback still succeeds;
- no submitted Sales Invoice/POS Invoice mutation occurs.

Do not replace merchant printer drivers merely to force WebUSB acceptance.

## Evidence record

Record each manual case with:

| Field | Required value |
| --- | --- |
| RetailEdge SHA | exact deployed commit |
| EdgeSuite UI SHA | exact deployed commit |
| Frappe / ERPNext versions | exact installed versions |
| Site | `retail.local` |
| Persona | user/role under test |
| Company / Branch | governed context |
| Case | journey step |
| Document(s) | exact document names created/read |
| Result | PASS / FAIL / BLOCKED |
| Evidence | screenshot/log/document reference where useful |
| Notes | defect or observed boundary |

Do not record credentials, API secrets or sensitive customer data in the repository.

## Hard-stop failures

MVP-C2 cannot pass if any required journey shows:

- permission or Branch/Company scope bypass;
- incomplete-user API access that should fail closed;
- duplicate Sales/Purchase/Payment/Journal/Stock posting;
- RetailEdge mutation of authoritative submitted accounting/stock truth outside ERPNext governance;
- wrong cashier/Branch transaction attribution;
- incorrect sale totals after permitted price/discount edits;
- shift expected-cash/reconciliation arithmetic inconsistent with the recorded transactions;
- report totals materially disagreeing with the authoritative documents for the same scope;
- asset/runtime failure on a required ordinary-user EdgeSuite surface;
- supported 1.0 printing path unable to produce an acceptable receipt on the merchant environment being accepted.

A hard-stop defect must be fixed on a bounded corrective branch from the tested candidate, then affected automated and manual cases must be rerun on the new exact head.

## Completion rule

MVP-C2 is complete only when:

1. the required start-to-close journey passes on `retail.local`;
2. supported 1.0 printing is physically accepted through at least one supported merchant path;
3. WebUSB remains explicitly preview/optional unless its separate physical matrix is passed;
4. the deployed exact SHA and evidence are recorded;
5. no unresolved release-blocking defect remains.

After that, continue to **MVP-C3 — Scale + fresh-install acceptance**. Do not skip directly to tag/release: `platform-baseline.json` should be promoted only through the later release-reconciliation/final-freeze steps after the remaining acceptance phases succeed.
