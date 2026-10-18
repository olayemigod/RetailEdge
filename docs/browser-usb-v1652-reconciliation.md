# Browser USB and 80mm receipt reconciliation

PR #213 is stacked on the proven RetailEdge PR #226 head `3f7baa5ab9706a9f3fce53fca39b57e74025b8a2`. Its exact EdgeSuite dependency is `95c982c21ed13cb453af220f68aaf579d4ae807b` from PR #45, stacked on PR #43. The platform remains Frappe 16.52.0 / ERPNext 16.51.1, with all other immutable app pins retained from the candidate manifest.

Reconciliation preserves native permissions, working-Branch scope, the shared information bar/Desk action, responsive SmartDate, adapter/dock boundaries and restored-merchant browser fixtures. The seven merge conflicts were only historical EdgeSuite SHA disagreements; workflow platform pins and USB transport assertions are both preserved. Neither predecessor PR nor any working merchant runtime is changed by reconciliation.

The feature remains: shared Serial/Bluetooth or WebUSB profile dispatch, strict saved binding/device matching, normal system-print fallback, and larger managed 80mm receipt item text with an idempotent v8 format refresh. The 58mm format and submitted accounting documents retain their existing semantics.

## Validation and physical acceptance

Run all required exact-head workflows against this precise EdgeSuite dependency: CI, candidate compatibility, upgrade/double migration/accounting integrity, browser personas and linters. Run the 80mm typography/58mm invariance and shared printing contract regressions locally. Existing successful Bluetooth/Serial printing is separate evidence and does not accept this feature.

Keep both feature PRs draft until physical QA validates: 80mm Product/Qty/Unit Price/Subtotal readability and fit; unchanged 58mm preview; explicit USB profile/device connection in a secure browser context; USB test print and receipt/cutter/barcode/encoding where hardware permits; safe claim failure when the Windows driver owns the interface; and successful normal Windows printing fallback with no submitted-invoice mutation. Do not replace drivers or assume a Windows USB queue is WebUSB-accessible.

Merge order remains predecessor #43/#226 after their own acceptance, then the separately accepted #45/#213 feature pair. Updating the branch lineage is not production deployment or physical acceptance.
