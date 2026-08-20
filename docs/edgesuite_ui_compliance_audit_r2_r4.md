# RetailEdge R2–R4 EdgeSuite UI Compliance Audit

## Purpose

Record the current EdgeSuite UI compliance state of the RetailEdge R2–R4 usability, reporting, dashboard, Guided Entry and Action Centre work before further Action Centre source expansion.

The audit distinguishes between:

- **EdgeSuite primary** — the normal RetailEdge navigation resolves to an EdgeSuite page/shell.
- **EdgeSuite implemented / QA-gated** — an EdgeSuite page exists and is covered by source-level tests, but the normal navigation intentionally remains on a native/legacy surface until browser/parity QA is complete.
- **Native by design** — ERPNext remains the authoritative form/report/workflow surface and RetailEdge deliberately drills into it rather than duplicating it.
- **Alignment required** — an EdgeSuite page is already governed and ready, but the primary product navigation still points to the older native surface.

## Compliance standard

An owner-facing RetailEdge page is considered EdgeSuite UI compliant when it:

1. Uses the canonical standalone EdgeSuite runtime (`edgeui.bundle.js`).
2. Uses `EdgeAppShell` as the single product shell and hides the competing native Frappe sidebar on the page.
3. Uses shared EdgeSuite reporting/dashboard components (`EdgeReportShell`, dashboard shell/cards, `EdgeLinkField`, shared export) where applicable instead of rebuilding ad-hoc tables or navigation chrome.
4. Uses shared RetailEdge business navigation/context rather than a second page-local menu.
5. Uses permission-aware, bounded backend providers and smart server-side Link searches.
6. Keeps accounting, stock and workflow truth in ERPNext/RetailEdge authoritative services.
7. Provides loading, error and empty-state behavior.
8. Keeps native ERPNext forms as explicit drill-throughs where ERPNext is the system of record.
9. Is responsive and remains subject to browser QA for mobile, dialogs, dropdown layering and dark mode.

## Current state

### EdgeSuite primary / compliant

- RetailEdge Business Hub
- Action Centre and Action Follow-Up controls
- Owner Dashboard
- Sales Overview / Sales Dashboard
- Money Overview
- Expense Overview / Expense Dashboard
- Branch Performance Dashboard
- Salesperson Performance Dashboard
- Sales by Item
- Sales Invoice Register
- Purchase Register
- Supplier Payables
- Customer Receivables implementation and reporting governance
- Stock Position
- Cash Movement
- Expense Register
- Guided Entry dialogs and Simple Master Quick Entry bridge

These surfaces use the shared EdgeSuite shell/report/dashboard architecture or are EdgeSuite-native Guided Entry surfaces. Native ERPNext forms reached from drill-through remain intentional.

### EdgeSuite implemented but QA-gated before primary navigation

- Stock Movement History
- Expense Review
- Cash Shift Verification
- Daily Sales Audit page

These pages exist as EdgeSuite implementations, use the canonical runtime/shared shell, and are covered by source-level tests. Their legacy/native navigation remains intentionally in place until the documented local browser/parity QA is complete.

Do **not** promote these routes merely to make navigation look uniform. Promotion requires source parity plus local browser QA.

### Native by design

The following remain valid native ERPNext/RetailEdge destinations when reached from EdgeSuite pages:

- Sales Invoice
- Purchase Invoice
- Payment Entry
- Stock Entry
- Stock Reconciliation
- Customer
- Supplier
- General Ledger
- Trial Balance
- Profit and Loss Statement
- Balance Sheet
- Cash Flow
- other detailed ERPNext accounting/stock forms and reports not yet replaced by a deliberately simplified RetailEdge experience

This is not an EdgeSuite compliance defect. EdgeSuite simplifies the operating experience without creating a second accounting or stock system of record.

## Alignment issue found

### Customer Receivables primary navigation

`customer-receivables` is already a governed EdgeSuite report surface with:

- a standard Frappe Page;
- `EdgeAppShell`;
- `EdgeReportShell`;
- `EdgeLinkField` smart filters;
- bounded provider/export governance;
- permission-aware ERPNext Sales Invoice accounting truth;
- invoice/customer drill-through;
- automated EdgeSuite compliance tests.

However, the main EdgeSuite `Customers` navigation still points `Receivables` to the native ERPNext `Accounts Receivable` Query Report.

This is a stale alignment issue, not an intentional preview gate.

Required correction:

1. Make **Customer Receivables** (`Page: customer-receivables`) the primary RetailEdge Customers navigation item.
2. Retain **Accounts Receivable (Detailed)** (`Report: Accounts Receivable`) as an explicit detailed ERPNext drill-down, mirroring the already-correct Supplier Payables pattern.
3. Add regression coverage that locks the EdgeSuite primary navigation target and prevents workspace/navigation sync from reverting it silently.
4. The compact native Frappe workspace may retain the detailed ERPNext report as a fallback if desired, but the EdgeSuite Business Hub/app-shell navigation must prefer the RetailEdge page.

## Stock Movement decision

Stock Movement History must remain on the legacy Query Report in normal navigation until its existing browser/parity checklist is completed. Its EdgeSuite page is a preview and should not be promoted as part of this audit alone.

Required local QA before promotion includes:

- opening balance parity;
- Stock Reconciliation handling;
- running balance parity;
- 1,000-row safety guard;
- filters and smart Link cascades;
- voucher drill-through;
- shared CSV/Excel/Print-PDF export;
- complete bounded dataset export rather than visible-page-only export;
- responsive/mobile layout.

## Review & Approvals decision

Action Centre is now the EdgeSuite management entry point and is role-gated. Existing detailed review/audit reports remain valid native/detail destinations until each corresponding EdgeSuite preview is browser-QA'd and promoted deliberately.

Action Follow-Up state must never mutate or falsely resolve the underlying accounting, stock, cash or workflow exception.

## Next implementation order

1. Correct Customer Receivables primary EdgeSuite navigation and add regression coverage.
2. Run CI and linters.
3. Complete local browser QA for the QA-gated reporting/review pages.
4. Promote only the pages that pass parity/browser QA.
5. Resume R4 Action Centre source expansion with Stock exceptions.
6. Add Bank/Reconciliation exceptions after the banking/reconciliation source contract is confirmed.
7. Implement unified Action Centre prioritisation using severity, financial exposure, age/overdue duration and branch/context without inventing alternate accounting calculations.

## Safety rules

- Do not rewrite submitted ERPNext accounting documents.
- Do not duplicate ERPNext ledger, stock or outstanding-balance calculations.
- Do not use `ignore_permissions` to make EdgeSuite pages work.
- Do not remove native detailed reports/forms merely because an EdgeSuite summary exists.
- Do not promote QA-gated pages before parity/browser verification.
- Keep smart forms server-validated and tenant/company/branch safe.
