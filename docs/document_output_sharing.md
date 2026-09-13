# RetailEdge Document Output & Sharing

## Goal

Provide one safe customer-document output experience for Quotation, Sales Order, Delivery Note and Sales Invoice without replacing ERPNext/Frappe document, Print Format, Letterhead, permission, email, stock or accounting truth.

## Architecture

- RetailEdge-owned EdgeSuite Page: `document-output-sharing`.
- Server service: `retailedge.document_output`.
- ERPNext/Frappe remains authoritative for:
  - business document state and permissions;
  - Print Formats;
  - Letterheads;
  - PDF rendering;
  - email transport and Communication linkage.
- RetailEdge adds Operating Company / Branch-aware discovery and a guided output workflow.

## Supported documents

1. Quotation
2. Sales Order
3. Delivery Note
4. Sales Invoice

These are the first customer-facing document types. Additional document types should only be added after their permission, privacy and business-use rules are explicit.

## Output flows

### Print Preview

The browser opens Frappe's authenticated print view using the selected ERPNext Print Format and Letterhead preference. RetailEdge does not render a second document template engine.

### PDF

`download_document_pdf` checks read + print permission, validates the selected Print Format against the source DocType, then renders through `frappe.get_print(..., as_pdf=True)`. The response is a private authenticated download; no public File record or public URL is created.

### Email

`send_document_email` requires read + print + email permission. The recipient address is validated, the PDF is rendered using the same native print engine, and Frappe's mail transport queues the message with the business document as its reference.

The source Quotation, Sales Order, Delivery Note or Sales Invoice is never modified by this operation.

### WhatsApp

The first implementation is deliberately user initiated:

1. Download the private PDF.
2. RetailEdge prepares a short document message and permitted contact mobile number when available.
3. RetailEdge opens WhatsApp / WhatsApp Web.
4. The user attaches the downloaded PDF manually.

RetailEdge does not make a private ERP document public merely to obtain a WhatsApp URL. A future CoreEdge-managed WhatsApp provider may replace this handoff while retaining the same permission and privacy contract.

## Smart form and security behavior

- Document searches are bounded to 20 Link results.
- Frappe Link search permissions remain active.
- Current Operating Company is applied when the DocType has a Company field.
- Current Operating Branch is applied when the source DocType has a supported branch field.
- Print Format choices are bounded and filtered to the selected source DocType.
- Disabled or cross-DocType Print Formats are rejected server-side.
- Frontend action visibility does not replace server permission checks.

## What this feature must never do

- Mutate submitted business documents.
- Create or change GL Entries, Stock Ledger Entries, Payment Entries or stock transactions.
- Introduce a parallel sales/document ledger.
- Use `ignore_permissions=True`.
- Commit the database manually.
- Publish private PDFs to `/files` or another public URL as a sharing shortcut.
- Bypass Frappe email or print permissions.
- Duplicate ERPNext Print Format or Letterhead configuration inside RetailEdge.

## Browser QA checklist

1. Open Document Output & Sharing from RetailEdge Business Hub.
2. Verify the page remains within EdgeSuite single-shell navigation.
3. Test Sales User, Sales Manager, Accounts User and restricted Branch user permissions.
4. Verify Operating Company / Branch changes alter document discovery appropriately.
5. Search each supported document type and confirm only permitted documents appear.
6. Preview Standard and one custom ERPNext Print Format.
7. Verify Letterhead on/off output parity with native ERPNext.
8. Download a PDF and compare it with native ERPNext print output.
9. Email a document to a controlled mailbox and verify the PDF attachment and Communication reference.
10. Verify a user without print permission cannot download.
11. Verify a user without email permission cannot send.
12. Open WhatsApp handoff and verify no private RetailEdge URL is embedded.
13. Check light mode, dark mode, desktop and mobile layouts.
14. Confirm source document `modified`, `docstatus`, totals, stock and accounting state do not change after Print/PDF/Email/WhatsApp actions.

## Future extension

- CoreEdge-managed email/WhatsApp delivery provider integration.
- Tenant-level default Print Format / Letterhead preferences where they do not override ERPNext permission truth.
- Auditable delivery outcome display based on authoritative Communication/provider logs.
- Additional customer documents after explicit security and workflow review.
