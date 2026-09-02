# E16 C20 — Supplier Scorecard & Governance

## Goal
Expose ERPNext's native Supplier Scorecard in RetailEdge Professional Purchasing without creating a parallel supplier-rating engine or widening permissions.

## Business context
RetailEdge already covers supplier collaboration, RFQ/quotation comparison, purchasing, receiving, supplier returns/debit notes, landed cost and incoming Quality Inspection. The remaining gap is governed supplier-performance visibility.

ERPNext v16 already provides Supplier Scorecard, Supplier Scorecard Period, scorecard criteria/variables/standings and supplier PO/RFQ warning/prevention flags. Those records are authoritative.

## Native ERPNext safety findings
- `Supplier Scorecard` and `Supplier Scorecard Period` are System Manager-only in ERPNext v16.
- Supplier Scorecard validation calculates the native score and standing.
- Updating the native scorecard can write `prevent_pos`, `prevent_rfqs`, `warn_pos` and `warn_rfqs` onto the Supplier.
- ERPNext creates/submits scorecard-period records through its own native engine.
- RetailEdge must therefore not calculate scores, create periods, alter standings, change Supplier block/warn flags, or broaden native DocType permissions.

## Scope
### EdgeSuite Professional Purchasing
Add a Supplier Scorecard & Governance section that:
1. checks native Supplier Scorecard capability for the current user;
2. allows a supplier to be selected using existing permission-aware Supplier filtering and Company/Branch/Supplier operating context;
3. when the user has native read permission, loads the supplier's native Supplier Scorecard and displays only authoritative read-only fields such as:
   - supplier;
   - supplier score;
   - status/standing;
   - evaluation period;
   - PO warning/prevention state;
   - RFQ warning/prevention state;
4. optionally loads recent submitted Supplier Scorecard Period records only when the current user has native read permission to them;
5. provides native route actions:
   - open existing Supplier Scorecard;
   - create a new native Supplier Scorecard only when the user already has native create permission;
   - open native Supplier Scorecard list/setup;
6. clearly warns that native scorecard standings can affect whether new Purchase Orders or RFQs are warned or prevented.

## Out of scope
- no RetailEdge supplier score formula;
- no custom supplier score/standing DocType;
- no automatic scorecard creation;
- no automatic Supplier flag changes;
- no creation/submission of Supplier Scorecard Period records;
- no modification of ERPNext Supplier Scorecard permissions;
- no Purchase Manager/Purchase User privilege escalation;
- no custom notifications or supplier sanctions in this slice;
- no submitted accounting/stock document mutation;
- no schema or patch unless a later implementation proves one is strictly required.

## Backend requirements
Create a small permission-preserving adapter, expected under `retailedge/supplier_scorecard_governance.py`.

Expected API shape:
- `get_supplier_scorecard_capability()`
  - reports native read/create capability for Supplier Scorecard and read capability for Supplier Scorecard Period;
  - must use Frappe permission APIs and never infer permission from role names alone.
- `get_supplier_scorecard_summary(supplier, company=None, branch=None)`
  - validates Supplier read access and RetailEdge company/branch operating scope;
  - re-reads the Supplier server-side;
  - requires native Supplier Scorecard read permission before returning scorecard data;
  - reads the scorecard whose authoritative name is the Supplier because ERPNext uses `autoname = field:supplier`;
  - returns only native read-only summary fields;
  - recent period rows, if included, must require Supplier Scorecard Period read permission and be bounded.

Do not call native score refresh/build methods from the RetailEdge read path. In particular, do not call `make_all_scorecards`, do not save the scorecard, and do not create/submit scorecard periods.

## Frontend requirements
- Keep the feature inside the existing EdgeSuite Professional Purchasing page.
- Prefer a dedicated child component to avoid disturbing C17–C19 flows.
- Use existing EdgeSuite components and permission-aware Supplier search.
- Do not use `frappe.ui.Dialog`, `frappe.prompt`, `frappe.msgprint`, or a classic parallel page.
- Opening/creating the scorecard should route to the native ERPNext `Supplier Scorecard` form/list.
- If native permission is absent, show a concise permission-preserving unavailable state; do not expose score/standing data.

## Safety rules
- ERPNext remains the sole supplier scorecard authority.
- No `ignore_permissions`.
- No direct write to Supplier scorecard governance flags.
- No `frappe.db.set_value` on Supplier governance fields from RetailEdge.
- No native scorecard refresh/build invocation from the read path.
- No GL Entry or Stock Ledger Entry writes.
- No submitted transaction mutation.
- No permission broadening through hooks/custom permissions.
- Company/Branch/Supplier context must be validated server-side, not trusted from the browser.

## Tests required
### Backend
- capability reflects native read/create/read-period permissions;
- no scorecard data returned without native Supplier Scorecard read permission;
- Supplier permission/context validated server-side;
- native summary returns authoritative score/status/period and PO/RFQ warn/prevent flags;
- period rows are bounded and permission-gated;
- no calls to `make_all_scorecards`, `.save()`, `.submit()`, `ignore_permissions`, direct Supplier governance-field writes, GL/SLE creation or manual commit.

### UI/static contract
- Supplier Scorecard & Governance section exists inside EdgeSuite Professional Purchasing;
- native read/create/list routes are present;
- existing Professional Purchasing, Return, Landed Cost and Quality Inspection flows remain intact;
- no Frappe dialog/prompt/msgprint/alert workflow is introduced;
- no custom score input or sanction toggle is exposed.

## Migration/backward compatibility
No migration should be required. Existing ERPNext scorecards, criteria, standings, periods and Supplier warn/prevent flags must remain untouched and immediately usable.

## Manual QA deferred
Manual/browser QA remains deferred to the cumulative reconciliation/QA branch. This slice must first pass the standard exact-head Theme, duplicate Linters, duplicate clean Frappe v16 CI and duplicate EdgeSuite compatibility gates.
