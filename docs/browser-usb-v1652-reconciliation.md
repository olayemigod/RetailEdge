# Browser USB and 80mm receipt reconciliation

## RetailEdge 1.0 support status — 20 October 2026

The implementation described below has since landed on the RetailEdge `version-16` line. The remaining physical WebUSB acceptance has **not** been completed on representative hardware.

For RetailEdge 1.0, Browser WebUSB is therefore classified as **optional / preview hardware support**, not a production-proven release promise and not an MVP release blocker.

The supported 1.0 printing boundary is:

- normal system printing / Print Document;
- configured Serial / Bluetooth direct receipt printing where the shared EdgeSuite printing runtime and target device support it;
- governed receipt formats already covered by automated and existing hardware evidence.

The WebUSB path remains available for controlled use, but its hardware-dependent physical acceptance is tracked separately. A merchant must always retain the normal system-print fallback when direct USB access is unavailable.

This boundary is recorded in `docs/mvp_c2_physical_merchant_acceptance_20261020.md`.

WebUSB is still classified by MDN as experimental, limited-availability and secure-context-only:

- https://developer.mozilla.org/en-US/docs/Web/API/WebUSB_API

## Historical reconciliation context

PR #213 was stacked on the proven RetailEdge PR #226 head `3f7baa5ab9706a9f3fce53fca39b57e74025b8a2`. Its exact EdgeSuite dependency is `4f6a0ee9ba8b6803ca81d179dcd45f343c6ad8a7` from PR #45, stacked on PR #43. The platform remains Frappe 16.52.0 / ERPNext 16.51.1, with all other immutable app pins retained from the candidate manifest.

Reconciliation preserves native permissions, working-Branch scope, the shared information bar/Desk action, responsive SmartDate, adapter/dock boundaries and restored-merchant browser fixtures. The seven merge conflicts were only historical EdgeSuite SHA disagreements; workflow platform pins and USB transport assertions are both preserved. Neither predecessor PR nor any working merchant runtime is changed by reconciliation.

The feature remains: shared Serial/Bluetooth or WebUSB profile dispatch, strict saved binding/device matching, normal system-print fallback, and larger managed 80mm receipt item text with an idempotent v8 format refresh. The 58mm format and submitted accounting documents retain their existing semantics.

## Validation and physical acceptance

The original feature acceptance required exact-head CI, candidate compatibility, upgrade/double migration/accounting integrity, browser personas and linters, plus the 80mm typography/58mm invariance and shared printing contract regressions. Existing successful Bluetooth/Serial printing is separate evidence and does not physically accept WebUSB.

When representative USB hardware is available, validate separately:

- 80mm Product/Qty/Unit Price/Subtotal readability and fit;
- unchanged 58mm preview;
- explicit USB profile/device connection in a secure browser context;
- USB test print and receipt/cutter/barcode/encoding where hardware permits;
- safe claim failure when the Windows driver owns the interface;
- successful normal Windows printing fallback with no submitted-invoice mutation.

Do not replace drivers or assume a Windows USB queue is WebUSB-accessible.

Passing this separate matrix may justify promoting WebUSB from preview/optional to a supported hardware claim in a later release. Until then, lack of WebUSB physical acceptance must not be represented as lack of RetailEdge 1.0 printing capability generally.
