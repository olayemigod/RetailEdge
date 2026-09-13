# RIR2F2C — Purchase Receipt Parity Gate

## Status

- **Authoritative line:** PR #55 / `qa/retailedge-reconciled-20260902`
- **Base checkpoint:** `6b02dd62c0eec2c3846b09671d01a23df82bbca9` (RIR2F2B frozen green)
- **Purpose:** prevent EdgeSuite-only users from entering a Purchase Receipt workflow that currently requires native ERPNext completion
- **Reporting:** remains blocked
- **Full Purchase Receipt EdgeSuite ownership:** not yet claimed

## Business decision

Purchase Receipt is a routine RetailEdge stock-buying operation. Long term it must have an EdgeSuite-first operating experience. The current implementation is not yet sufficient to declare that ownership.

Professional Purchasing can safely identify Purchase Orders ready to receive and can call ERPNext's standard `make_purchase_receipt` mapper to create a draft Purchase Receipt. However, after draft creation the current UI routes directly to the native ERPNext Purchase Receipt form for review and completion. EdgeSuite-only users are intentionally blocked from that native form by the operational guard.

That combination creates a dead-end: a normal EdgeSuite-only user can be offered **Prepare Receipt**, create a draft, and then be unable to complete the workflow.

RIR2F2C therefore treats Purchase Receipt as **PARITY_BLOCKED_NATIVE_COMPLETION** until a safe EdgeSuite completion surface exists.

## Safety behavior in this slice

1. **EdgeSuite-only users**
   - do not see or activate `Prepare Receipt` from Professional Purchasing;
   - do not see or activate the native `Purchase Receipts` list handoff;
   - cannot use a render-race click to create a receipt draft before the restricted presentation guard catches up;
   - continue to be blocked from native Purchase Receipt routes by the shared EdgeSuite-only guard.

2. **Native-Desk-authorized users**
   - retain the existing ERPNext-based receipt workflow;
   - the actions are explicitly labeled as advanced ERPNext handoffs rather than presented as normal RetailEdge-owned completion:
     - `Advanced: Prepare Receipt in ERPNext`
     - `Advanced: Purchase Receipts in ERPNext`.

3. **ERPNext truth remains unchanged**
   - `prepare_purchase_receipt_draft()` still uses ERPNext's standard Purchase Order → Purchase Receipt mapper;
   - receipt creation remains draft-first;
   - no submission, Stock Ledger, General Ledger, valuation, quantity, warehouse, serial/batch, quality, or accounting semantics are rewritten in this slice;
   - no roles or ERPNext permissions are broadened.

## Why native Purchase Receipt is not removed from navigation yet

Unlike Purchase Order, RetailEdge does not currently have a complete EdgeSuite Purchase Receipt read/edit/completion surface. The existing native form remains necessary for authorised advanced users and for operational continuity while parity is built.

Removing the native peer now would falsely claim product ownership and would strand valid advanced workflows.

## RIR2F2D exit criteria — EdgeSuite Purchase Receipt ownership

Before Purchase Receipt can become `EDGE_PRIMARY`, the implementation must provide a bounded but operationally complete EdgeSuite receipt flow that preserves ERPNext validation and document lifecycle. At minimum, the design must explicitly audit and safely handle the applicable cases for:

- Purchase Order source and remaining receivable quantities;
- accepted and rejected quantities where ERPNext requires them;
- target and rejected Stock Locations/Warehouses;
- posting date/time controls and branch/company attribution;
- serial/batch or Serial and Batch Bundle requirements;
- quality-inspection requirements;
- stock UOM/conversion and ERPNext quantity validation;
- supplier delivery references where operationally required;
- subcontracted Purchase Orders as a deliberate supported or excluded case;
- draft save, reload/resume, validation errors, and standard ERPNext submission;
- permission-aware and Branch-safe server validation on every write;
- no direct Stock Ledger or General Ledger manipulation.

The EdgeSuite surface does not need to clone every advanced ERPNext field. It must expose enough information and controls for the supported everyday receipt cases and fail clearly into an explicit advanced workflow for deliberately unsupported cases.

## Tests required for this gate

Automated contract coverage must verify that:

- the current Vue workflow still requires native Purchase Receipt completion after draft preparation, proving parity has not been falsely claimed;
- EdgeSuite-only users have both presentation and capture-phase protection against `Prepare Receipt` and native receipt-list actions;
- Native-Desk users receive explicit advanced labels;
- the native Purchase Receipt peer remains available until RIR2F2D parity is complete;
- no Purchase Receipt backend posting semantics are changed by this safety slice.

## Manual QA required before final RIR2E sign-off

Test at least:

- EdgeSuite-only Purchase User with one Branch;
- EdgeSuite-only Purchase User with multiple permitted Branches;
- EdgeSuite-only restricted-zero-Branch persona;
- Native-Desk-authorized Purchase Manager;
- PO ready to receive;
- PO already fully received;
- subcontracted PO;
- attempted rapid click while the page is rendering.

For EdgeSuite-only personas, no receipt draft should be created from a blocked action. For Native-Desk personas, the advanced handoff may continue to ERPNext and must preserve normal ERPNext validation.
