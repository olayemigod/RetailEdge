# RIR2F3F41 — Landed Cost Voucher EdgeSuite Ownership

## Goal

Close the remaining standard Professional Purchasing completion gap for landed cost while preserving ERPNext v16 Landed Cost Voucher as the sole valuation, stock-ledger and accounting authority.

## Audit Result

The existing C18 helper is safe but incomplete for EdgeSuite-only users:

- source discovery is permission-, Company-, Branch- and Supplier-scoped;
- ERPNext native `make_lcv()` is used to build one in-memory Landed Cost Voucher;
- the current helper does not insert, save, submit or mutate the submitted source;
- ordinary completion still requires routing to the native Landed Cost Voucher form;
- the EdgeSuite-only operational guard therefore hides the whole landed-cost panel.

F3F41 must own only the common standard case inside EdgeSuite and keep advanced native ERPNext explicitly available to Native-Desk-capable users.

## Standard EdgeSuite Contract

### Supported source

Exactly one:

- submitted, non-return Purchase Receipt; or
- submitted, non-return Purchase Invoice with `update_stock = 1`.

The source must remain inside the current permitted Company/Branch scope. Supplier, Company, receipt rows, item quantities/rates/amounts and source linkage are always rebuilt server-side.

### Supported allocation

Standard EdgeSuite supports:

- `Amount`; or
- `Qty`.

`Distribute Manually` remains Advanced ERPNext because it permits item-level authoritative allocation edits.

### Supported landed-cost charge input

Each standard charge row accepts only:

- `expense_account`;
- `description`;
- positive `amount`.

The expense account selector must mirror ERPNext's native allowed account types, be non-group/non-disabled, belong to the source Company, respect read permission, and be revalidated server-side.

The browser must not provide or control account currency, exchange rate, base amount, total landed cost, applicable item charges, source item values, Company, Supplier, posting state, workflow state, Stock Ledger or GL effects.

ERPNext `LandedCostVoucher.validate()` remains authoritative for:

- account currency and exchange rate;
- base charge amount;
- mandatory accounting dimensions;
- receipt/source validity;
- item-source validity;
- cost centres;
- total charges;
- proportional allocation;
- applicable charges per item.

### Persistence stages

1. **Review**
   - persistence-free;
   - rebuild native `make_lcv()`;
   - append only validated charge inputs;
   - run native Landed Cost Voucher validation in memory;
   - return ERPNext-computed totals and item allocations plus source snapshot and workflow mode.

2. **Start / save standard draft**
   - POST;
   - lock and re-read exact source;
   - revalidate permission, Company/Branch scope, source lifecycle, charge accounts and source snapshot;
   - rebuild and validate the native LCV again;
   - inspect existing draft Landed Cost Vouchers linked to the exact source;
   - reuse exactly one readable draft only when it is standard-equivalent;
   - fail closed on multiple, unreadable or non-standard drafts;
   - otherwise insert exactly one complete ERPNext Landed Cost Voucher draft under normal permissions;
   - return saved draft and authoritative Workflow readiness.

3. **No active Frappe Workflow**
   - a separate scoped Submit action locks/re-reads the exact saved LCV and source;
   - verifies exact single-source standard equivalence and stale target snapshot;
   - uses normal ERPNext `submit()`;
   - a retry against the same already-submitted LCV returns its submitted result and never creates/submits another voucher.

4. **Active Frappe Workflow**
   - direct standard Submit is unavailable;
   - saved draft actions are only those returned by Frappe Workflow;
   - each action locks/revalidates source + LCV, standard equivalence, stale target snapshot and expected workflow state;
   - transition delegates to `retailedge.workflow_actions.apply_document_workflow_action`;
   - Frappe `apply_workflow()` remains authoritative.

## Standard-Case Blockers / Advanced ERPNext

Fail standard EdgeSuite handling closed when any of these apply:

- manual distribution;
- more than one source receipt/invoice;
- Stock Entry or Subcontracting Receipt source;
- vendor invoice claim rows;
- fixed-asset source items;
- user-edited source item mapping;
- item removal or manual applicable-charge edits;
- non-positive standard charge amount;
- unsupported/foreign Company account;
- native validation requiring accounting/dimension data not represented by the standard flow;
- cancellation, amendment or submitted-document editing;
- multiple or non-standard existing linked draft LCVs.

Native Advanced preparation remains the existing persistence-free `make_lcv()` handoff and is shown only when final Native Desk capability is available.

## UI Requirements

- The Landed Cost panel must no longer be hidden merely because the user is EdgeSuite-only.
- Ordinary users can:
  1. choose eligible Purchase Receipt or stock-updating Purchase Invoice;
  2. choose Amount or Qty distribution;
  3. add/remove standard landed-cost charge rows;
  4. select a filtered expense account;
  5. enter description and positive amount;
  6. review ERPNext-computed item allocations;
  7. save/reuse the standard LCV draft;
  8. submit directly when no Workflow exists, or use only returned Workflow actions when one exists.
- Native Desk-capable users retain **Advanced: Prepare in ERPNext** for unsupported cases.
- Do not route EdgeSuite-only users to the Landed Cost Voucher form.

## Safety Rules

- ERPNext Landed Cost Voucher is the only persisted business document.
- Do not duplicate `update_landed_cost()`, allocation maths, Stock Ledger reposting or GL reposting.
- Do not directly create/update GL Entry, Stock Ledger Entry, Serial No valuation or receipt valuation fields.
- Do not mutate submitted Purchase Receipt/Purchase Invoice from RetailEdge.
- Do not call `update_landed_cost()` directly.
- Do not use `ignore_permissions`, `ignore_mandatory` or manual database commit.
- Do not accept browser-provided authoritative receipt items, totals, Company, Supplier, exchange rate, base amount or applicable charges.
- Restricted-zero Branch access must fail closed.

## Files to Inspect / Change

Primary:

- `retailedge/landed_cost_allocation.py`
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- `retailedge/retailedge/page/professional_purchasing/professional_purchasing.js`
- focused F3F41 backend/contract tests
- this contract

No DocType, patch or schema change is expected.

## Tests Required

- current C18 unsaved advanced handoff remains persistence-free;
- account search/filter mirrors ERPNext account-type/company restrictions;
- server rejects group/disabled/wrong-company/unsupported accounts;
- standard review is persistence-free and uses native `make_lcv()` + native LCV validation;
- Amount and Qty supported; manual distribution blocked to Advanced;
- fixed assets/vendor invoices/multiple sources/non-standard item mapping fail closed;
- review returns only ERPNext-computed totals/applicable charges;
- start is source-locked/stale-protected and creates at most one standard draft;
- exactly one matching draft is reused idempotently;
- multiple/non-standard/unreadable draft collisions fail closed;
- no-Workflow Submit revalidates and calls native `submit()`;
- already-submitted retry returns the existing voucher without another submit;
- active Workflow blocks direct submit and uses F3F27 transitions with expected state;
- EdgeSuite-only operational guard no longer hides the standard landed-cost panel;
- UI does not assign workflow/docstatus or calculate allocation/base currency values itself;
- Advanced native handoff is shown only with Native Desk capability.

## Out of Scope

- manual item-level allocation;
- vendor invoice landed-cost claims;
- fixed-asset landed cost;
- Stock Entry/Subcontracting Receipt guided source;
- custom accounting-dimension input UI;
- cancellation/amendment;
- multi-source voucher composition;
- landed-cost forecasting/import documentation;
- reporting expansion;
- manual browser/persona QA before consolidated RIR2E acceptance.

## Freeze Rule

F3F41 may become **CODE-FROZEN / QA-PENDING** only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and EdgeSuite UI Candidate Compatibility all pass on the same exact implementation head.
