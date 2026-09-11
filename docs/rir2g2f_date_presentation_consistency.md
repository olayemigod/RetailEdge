# RIR2G2F — Date Presentation Consistency

## Goal

Remove remaining raw ISO date leakage from ordinary RetailEdge EdgeSuite UI pages while preserving ISO values for APIs, filters, sorting, keys, persistence and ERPNext/Frappe business logic.

## Audit result

The governed EdgeReportShell surfaces already carry typed Date/Datetime columns through the shared reporting runtime and are not patched here.

The remaining confirmed raw display leaks are bounded to:

1. Forecasting & Planning
   - monthly planning rows
   - known-due commitments
   - inventory planning rows
   - scenario performance rows
2. Project Operations
   - Task expected end
   - transaction timeline date
   - Project Cash In posting date
   - Project Cash Out posting date
3. Inventory Insights
   - profitability scope range
4. Inventory Intelligence
   - demand-evidence scope range
5. Customer Sales Intelligence
   - sales-period scope range
6. Customer Opportunity Intelligence
   - current comparison range
   - prior comparison range
7. Sales Forecast
   - history scope range
8. Sales Dashboard
   - recent invoice posting date

## Presentation contract

- Introduce one small RetailEdge frontend date-display helper.
- The helper must use Frappe's user-aware date conversion (`frappe.datetime.str_to_user`) rather than hard-code DMY/MDY/YMD ordering.
- Empty values render as the existing em dash fallback.
- Internal values remain unchanged:
  - API/filter values remain ISO;
  - sort keys remain raw data values;
  - row keys remain raw identifiers/dates;
  - backend payloads remain unchanged.
- Only user-visible text is formatted.
- Existing native `<input type="date">` values remain ISO because browsers require that format.
- Existing pages that already format dates correctly (Payment Management, Professional Purchasing, Customer 360, Stock Movement History and EdgeReportShell reports) are not rewritten.

## Safety rules

- No accounting, stock, payment, forecasting calculation, workflow or permission semantics change.
- No branch/company cascade change.
- No backend API or schema change.
- No submitted document mutation.
- No `ignore_permissions`.
- No manual database commit.
- No shared EdgeSuite UI runtime modification.
- Do not reopen frozen G2A–G2E2 contracts.

## Tests required

- shared helper delegates to Frappe user date formatting;
- all eight audited surfaces use the helper for the identified visible dates;
- raw ISO values remain in filters, row keys and API payloads;
- no backend files are changed;
- existing state, sorting, responsive-table and reporting contracts remain green.

## Freeze gate

Freeze G2F only when one exact authoritative head passes:

1. RetailEdge Theme Compatibility;
2. Linters / Semgrep / vulnerable dependency audit;
3. Clean Frappe v16 CI;
4. EdgeSuite UI Candidate Compatibility.

Manual browser/persona acceptance remains deferred to consolidated RIR2E.
