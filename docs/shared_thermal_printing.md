# RetailEdge direct receipt printing

RetailEdge adopts the shared EdgeSuite printing runtime rather than implementing Bluetooth or
ESC/POS itself.

## Ownership

- **RetailEdge** owns the receipt's business meaning, permitted source documents, item/totals layout,
  and the decision that a submitted document may be printed.
- **EdgeSuite** owns printer profiles, device binding, Web Serial, ESC/POS byte generation, printer
  connection state, and the Devices & Printing setup experience.
- ERPNext remains authoritative for the Sales Invoice / POS Invoice and its permissions.

## First supported documents

- Sales Invoice
- POS Invoice

Only submitted documents are eligible for direct receipt output. The server endpoint requires both
read and print permission on the source document.

## User flow

A submitted sale exposes **Print Receipt**. RetailEdge:

1. resolves the active EdgeSuite Receipt profile for the current RetailEdge/company/branch context;
2. restores the printer already authorised in that browser/device;
3. fetches a permission-checked logical receipt payload from RetailEdge;
4. applies the EdgeSuite paper/profile options;
5. sends the normalized receipt to `EdgeSuiteUI.print.printReceipt()`.

If the local printer has not been selected or cannot be restored, the user is offered
**Devices & Printing** instead of falling back to raw browser device APIs.

**Print Document** remains the existing ERPNext/Frappe print-preview route. Direct thermal receipt
printing is additional, not a replacement for A4/PDF/document output.

## Cash drawer safety

Ordinary Print Receipt and reprint actions do not pulse the cash drawer. Drawer opening is reserved
for a later payment-aware sale-completion policy where RetailEdge can prove the business condition
for opening it.

## Failure boundary

Printer failure does not alter, cancel, or roll back the Sales Invoice/POS Invoice. A completed ERP
transaction remains completed and the user may reconnect and reprint.

## Browser tabs and the Document Output page

**Print Receipt** on **Professional Selling → Print & Share → Document Output & Sharing**
uses the same EdgeSuite shared direct receipt adapter as POSNext; it does not
call Web Serial itself. **Print Document** is different: it uses the normal
browser/Frappe print preview, not the saved MPT-II serial connection.

When using a supported EdgeSuite tab-handoff build, a POSNext tab and a Desk
Document Output tab on the **same HTTPS origin** may safely share the
authorized printer, but each tab has its own live serial-port object. A
browser-level exclusive lease coordinates handoff of the *idle* connection;
a busy print must not be interrupted. A page with an outdated EdgeSuite
bundle, a different origin (HTTP vs HTTPS, another hostname or port), or an
external Windows/phone Bluetooth connection may not participate.

RetailEdge restores the binding by the document's server-authorized
Company/Branch print profile, and verifies that the restored connection
matches the **exact profile** before sending any data. A generic Bluetooth
Serial Port Profile service UUID is not a unique printer identity. If a
different tab still owns the printer, show its actionable error and do
not navigate automatically into another competing setup tab.

QA matrix:
- Set up MPT-II at `https://retail.local/app/edge-printing`; test the
  physical printer and leave the setup tab connected but idle.
- Open Document Output & Sharing from Professional Selling; select a
  submitted Sales Invoice and click **Print Receipt**, not **Print Document**.
  Verify the 58mm paper receipt and that the saved source invoice is unchanged.
- Without closing the Desk tab, print the same submitted invoice from POSNext
  and back from Document Output. Confirm each tab releases the idle port, no
  Windows Bluetooth socket collision, no wrong-branch output or duplicate
  transaction.
- Switch browser tab focus before and after printing. Confirm a busy
  in-flight job is not stolen by another tab. Check a restricted cashier's
  positive and negative document print permissions.
- Independently verify browser Print Document/PDF/WhatsApp remains unaffected.
  Test light/dark UI feedback. Do not interpret `bytesWritten` alone as
  physical output.

Dependency: EdgeSuite UI cross-tab handoff is proposed in shared Draft PR #53.
This RetailEdge fix is backward compatible, but full two-tab physical
acceptance requires the tested EdgeSuite candidate and RetailEdge candidate
on the same `retail.local` bench. The current RetailEdge CI pinned shared
platform baseline is not silently changed by this slice.
