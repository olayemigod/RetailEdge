# RIR2F2D1 — Purchase Receipt EdgeSuite Preflight

## Goal

Introduce the first safe EdgeSuite Purchase Receipt parity slice without creating, saving, submitting, cancelling, or mutating any Purchase Receipt.

RIR2F2D1 replaces the EdgeSuite-only dead end with a permission-aware **Review Receipt** preview. ERPNext remains the sole stock/accounting authority.

## Business behaviour

From the Professional Purchasing Purchase Order queue:

- a receivable PO exposes **Review Receipt**;
- RetailEdge asks ERPNext to build the standard PO → Purchase Receipt mapping in memory;
- the user sees supplier, company, branch, remaining receipt lines, quantities, UOM and receiving Stock Locations;
- no draft is inserted;
- no Stock Ledger Entry or General Ledger Entry can be produced;
- no submission occurs.

Native-Desk-authorised users may deliberately choose **Advanced: Prepare in ERPNext** from the preview. EdgeSuite-only users do not receive that escape.

The native Purchase Receipt list remains advanced/native because RetailEdge does not yet own receipt history/detail parity.

## Standard-path preflight

The preview classifies a mapped receipt as standard only when no hard blocker is found.

RIR2F2D1 treats these as advanced blockers:

- subcontracted Purchase Order;
- serial-number-controlled Item;
- batch-controlled Item;
- Item requiring purchase quality inspection;
- rejected quantity already present in the mapped receipt;
- no receivable lines remaining.

This list is intentionally conservative. It may be narrowed only with ERPNext-backed tests proving the workflow can be completed without bypassing stock controls.

## Server authority

`retailedge.professional_purchase_receipt.get_professional_purchase_receipt_preview`:

1. requires a named existing Purchase Order;
2. checks Purchase Order read permission;
3. requires a submitted Purchase Order;
4. requires Purchase Receipt create permission;
5. revalidates the PO Branch against the authenticated user where branch attribution exists;
6. calls ERPNext `make_purchase_receipt()`;
7. inspects the in-memory mapped receipt and Item stock-control metadata;
8. returns preview data and blockers only.

It must not call `insert`, `save`, `submit`, `db_set`, or another persistence/posting path.

## Relationship to RIR2F2C

RIR2F2C blocked EdgeSuite-only receipt creation because the only completion route was native ERPNext Desk.

RIR2F2D1 does not weaken that safety decision. It changes the normal EdgeSuite action from an inaccessible native workflow to a non-persisting preview. The actual EdgeSuite receipt posting capability remains gated.

## Next bounded slice — RIR2F2D2

RIR2F2D2 may introduce a standard receipt posting workflow only after this preflight contract is green. It must, at minimum:

- keep ERPNext `make_purchase_receipt()` as the mapping source;
- revalidate Company, Branch and receiving Warehouse server-side;
- accept only bounded quantity/warehouse input needed by the standard workflow;
- fail closed when serial/batch, quality inspection, subcontracting or other unsupported controls are present;
- use ERPNext validation and submission as the stock truth;
- prevent duplicate receipt posting / stale remaining-quantity assumptions;
- provide explicit browser QA for partial and full receipt scenarios;
- never mutate an already submitted Purchase Receipt.

## Out of scope

- Purchase Receipt submission in EdgeSuite;
- serial/batch bundle capture;
- Quality Inspection creation/acceptance;
- subcontracting receipts;
- returns/rejected-stock workflows;
- landed cost;
- Purchase Invoice changes;
- Purchase Order posting changes;
- reports;
- Business Hub redesign;
- branch contract changes.

## QA acceptance for D1

- EdgeSuite-only user can open **Review Receipt** from a receivable PO.
- Opening and closing the preview creates no Purchase Receipt.
- Preview data comes from ERPNext's PO→receipt mapper.
- Standard item rows display mapped remaining quantities and Stock Locations.
- Serial/batch/quality/subcontracting cases show a clear advanced-handling blocker.
- EdgeSuite-only user has no native receipt escape from the preview.
- Native-Desk user may deliberately choose the advanced ERPNext handoff.
- Native Purchase Receipt route remains blocked for EdgeSuite-only accounts.
- Existing PO creation/ownership behavior is unchanged.
- Console and network are clean in light and dark mode.
