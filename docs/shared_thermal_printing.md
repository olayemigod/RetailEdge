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
