# RetailEdge MVP Production Copy Audit — 2026-10-06

## Goal

Ensure normal RetailEdge users see business language rather than internal implementation vocabulary, release-lineage codes, framework names, developer diagnostics, or raw source identifiers.

This audit is presentation-focused. Internal API names, source keys, DocType names, routes, compatibility metadata, database values, accounting documents, and release-lineage identifiers remain unchanged unless they are directly rendered to users.

## Production copy policy

Normal RetailEdge operational UI should not expose implementation language such as:

- internal release codes (`R8`, `R9`, `R10`, `R11`, `R12`, `RIR*`, etc.);
- raw source keys such as `r11_customer_opportunity`;
- `EdgeSuite`, `CoreEdge`, or `Frappe` as implementation details;
- `Native Desk` as a user-facing capability name;
- `ERPNext` where the user only needs business context such as accounting records, advanced settings, submitted sales, stock records, or a full workflow;
- engineering phrases such as `provider`, `canonical`, `source of truth`, `server-derived`, or `dry run` when a business description is clearer;
- raw traceback, module, method, route, or database wording.

Explicit administrator/developer documentation may retain technical terminology. Internal compatibility metadata may also retain it when it is not rendered.

## Confirmed defect that triggered this audit

Action Centre converted its internal source key to title case. This meant:

- `r11_customer_opportunity` rendered as `R11 Customer Opportunity`;
- the metadata line was built with a hard-coded separator, allowing an unnecessary trailing/intermediate `·` when a label was empty.

The backend source key is intentionally retained for action fingerprint and compatibility stability. The presentation layer now owns the customer-facing label.

## Fixed in this branch

### Action Centre

- Added explicit customer-facing labels for known action sources.
- Strips release prefixes from unknown fallback source keys rather than presenting them.
- Builds metadata labels from non-empty values only.
- Handles current, period, and forecast time bases with business wording.
- Removed `Native Desk` wording from workflow access messages.
- Renamed unavailable-source presentation to user-oriented information/access wording.

### Customer & Sales Intelligence

- Removed visible `ERPNext` and `R8` terminology from subtitle, result notes, and export fallbacks.
- Preserved the underlying submitted-sales, receivables, and transactional-cost semantics.

### Customer Retention & Opportunity Intelligence

- Removed `ERPNext` terminology from receivable/source presentation and export fallbacks.

### Discount & Sales Quality

- Removed `ERPNext` and `R8` terminology from screen notes and export metadata.
- Kept the distinction between recorded transaction margin and financial profit.

### Inventory Intelligence

- Removed `ERPNext` terminology from subtitle, replenishment notes, and export metadata.
- Retained the underlying stock, demand, reorder, and valuation sources.

### Forecasting & Planning

- Removed visible `R12`, `ERPNext`, `Native Desk`, and `EdgeSuite` wording.
- Reworded budget, accounting, scenario, and advanced-access explanations in business language.
- Did not change planning calculations, scenario storage, permission flags, accounting safeguards, or navigation behavior.

### Retail Settings

- Price-list priority descriptions no longer mention `ERPNext User Permissions` or `ERPNext Selling/Buying Settings`.
- `CoreEdge` labels/descriptions are presented as `Platform` / `Platform Services` while the existing fieldnames remain stable.
- Existing sanitization of RetailEdge/EdgeSuite/ERPNext/Frappe metadata is preserved.

### Company Profile

- `ERPNext country` → `Country`.
- Advanced accounting/statutory copy now refers to advanced Company settings/configuration.
- `Advanced: Open Company in ERPNext` → `Open Advanced Company Settings`.
- Advanced access notice no longer exposes the implementation platform.

### Bank reconciliation confirmation

- Primary action is now `Reconcile Match` instead of `Reconcile Through ERPNext`.
- Confirmation text explains the fresh safety check and accounting action without exposing the underlying platform.
- Reconciliation execution and approval safety are unchanged.

## Confirmed remaining production-copy debt

The following areas still contain implementation-oriented wording and require follow-up before declaring the whole application copy-clean.

### Professional Purchasing

High-priority examples include:

- `ERPNext remains authoritative...` in page/hero descriptions;
- `canonical ERPNext return` / `Frappe Workflow`;
- `ERPNext-compatible landed-cost account types`;
- `Advanced: Prepare in ERPNext`;
- `ERPNext allocation`;
- `ERPNext sourcing demand` / `ERPNext order truth`;
- user-visible action errors such as `ERPNext could not prepare...`;
- landed-cost notices that expose ERPNext execution internals.

These should be replaced with business wording such as `accounting and stock records`, `configured approval workflow`, `advanced review`, `allocated cost`, and `full purchasing workflow`. Internal routing and document ownership must not change.

### Advanced workflow/blocker messages

Repository search found customer-facing `Advanced ERPNext` language in or around:

- payment history and advanced payment paths;
- incoming quality inspection;
- purchase receipts and purchase returns;
- purchase/sales invoice completion;
- internal transfers;
- guided payment;
- supplier quotation and supplier document flows;
- stock adjustment / transfer surfaces;
- Professional Selling and related overlays.

Typical replacement rule:

- `requires Advanced ERPNext review` → `requires advanced review` or `requires the full <business workflow>`;
- `Open in ERPNext` → `Open Advanced Details` / `Open Full Record` / workflow-specific business action;
- retain the same permission and handoff behavior.

### Report Center

Confirmed merchant-facing descriptions still include examples such as:

- `R8 transactional contribution`;
- `ERPNext salesperson commission detail`;
- `governed ERPNext purchasing workflow`;
- `Open ERPNext Stock Balance/Stock Ledger/...`;
- `ERPNext General Ledger truth`;
- `Open ERPNext Accounts Receivable/Payable...`.

Targets and `native_desk` capability flags should remain unchanged; descriptions should be rewritten only.

### Bank matching source confirmation

`bank_matching_reconciliation.js` still emits the legacy interception phrase containing `ERPNext`. The confirmation override hides it from the user, but the source phrase should be replaced in a later cleanup and the interceptor contract updated at the same time.

## Terms that are not automatically defects

Do not mechanically rename these in backend/internal code:

- `canUseNativeDesk` permission flags;
- `r11_*`, `r12_*`, and other source/action keys;
- DocType names;
- API/module names;
- routes;
- `source_of_truth` metadata used only internally;
- comments and engineering documentation;
- ERPNext/Frappe imports and framework API calls.

Renaming those can break compatibility without improving user experience.

## Regression protection

`retailedge/tests/test_production_copy_contract.py` now protects the first cleaned MVP surfaces from the specific release/platform wording regressions addressed in this branch.

The test deliberately does not ban technical terms repository-wide because legitimate backend code and engineering documentation must retain implementation identity.

## Manual QA checklist

Use at least one normal operational user and one authorised manager/admin persona.

1. Open Action Centre and confirm customer/sales/planning source labels never show `R11`, `R12`, raw underscores, or a dangling `·`.
2. Check Action Centre current-period and forecast items for correct time-basis wording.
3. Open Customer & Sales Intelligence, Customer Retention & Opportunity, Discount & Sales Quality, Inventory Intelligence, and Forecasting & Planning. Review headings, helper text, empty states, exports, errors, and advanced-access tooltips.
4. Open Settings → Platform Integration and Price List Governance. Confirm no `CoreEdge`, `ERPNext`, `EdgeSuite`, or `Frappe` branding leaks through labels/descriptions.
5. Open Company Profile as a normal user and as an advanced-authorised user. Confirm the page uses business language and the advanced button still opens the same underlying Company record only when permitted.
6. Run a bank reconciliation through the final confirmation. Confirm the button says `Reconcile Match`, safety wording is clear, and execution behavior is unchanged.
7. Continue the audit through Professional Purchasing, payments, stock, quality inspection, selling completion, and Report Center before the final MVP production-copy sign-off.

## Safety / non-regression rules

- Do not rename internal source/action keys to solve presentation problems.
- Do not mutate submitted accounting documents.
- Do not weaken permission, approval, branch, company, or reconciliation safeguards.
- Do not replace business-specific document names such as Sales Invoice, Purchase Invoice, Payment Entry, Journal Entry, or Stock Ledger when the document identity itself is useful to the user.
- Prefer `advanced review`, `full workflow`, `accounting records`, `stock records`, `platform services`, or the specific business action over framework implementation terminology.
