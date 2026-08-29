# RetailEdge Transaction Workspace + POSNext Integration

## Goal

Provide one EdgeSuite transaction entry point for sales, purchasing, stock and POS while preserving ERPNext/POSNext as the authoritative transaction engines.

## Architecture

- Frappe Page wrapper: `transaction-workspace`
- EdgeSuite runtime: `edgeui.bundle.js`
- Product bundle: `transaction_workspace.bundle.js`
- Vue experience: `TransactionWorkspace.vue`
- Shell: `EdgeAppShell` + `EdgePageLayout`
- Server context: `get_transaction_workspace_context()`
- POS online preflight: `prepare_pos_launch()`

## Transaction behaviour

The workspace reuses existing guided components for:

- Sales Invoice
- Purchase Invoice
- Stock Transfer

Sales Order, Delivery Note, Purchase Order and Purchase Receipt remain native ERPNext full-form flows until their dedicated professional transaction implementation. This avoids duplicate editors and preserves ERPNext workflow/accounting truth.

## POS provider boundary

RetailEdge selects the installed POS provider using the existing `pos_runtime` capability resolver.

- POSNext remains the POS engine when its shift DocTypes are installed.
- ERPNext Point of Sale remains the fallback provider.
- RetailEdge does not iframe or copy the POSNext frontend.
- RetailEdge does not duplicate ProcessEdge POSNext Extension features such as editable selling rate or posting-date controls.

## Operating Context safety

When online, `prepare_pos_launch()` validates the current Operating Company and Branch before launch.

For POSNext, an active opening shift must match:

- Operating Company
- Operating Branch
- Branch Setup POS Profile, when configured

For native ERPNext POS, an active POS Opening Entry is checked with permission-aware `frappe.get_list` and its Company/POS Profile must remain compatible with the Operating Context.

The preflight is read-only. It does not create, update, close, save or submit POS documents and does not mutate Operating Context.

## Offline POSNext rule

RetailEdge must not make internet connectivity a prerequisite for POSNext offline operation.

- When online, Start POS uses the RetailEdge server preflight.
- When the browser is offline, POSNext may launch directly using the already-known POSNext route.
- If connectivity drops during preflight, the browser may use the POSNext offline route rather than blocking the cashier.
- Online server validation failures must not be bypassed.
- Native ERPNext POS does not claim the same offline capability.
- The direct provider-aware `Start POS` navigation item remains available alongside Transaction Workspace so a cashier is not dependent on the Transaction Workspace bundle being cached before reaching POSNext.

RetailEdge does not itself implement POSNext offline storage or sync. POSNext remains responsible for those mechanics.

## EdgeSuite rule

Transaction Workspace is a RetailEdge-owned Page and must remain EdgeSuite-based. The repository governance test requires:

- `edgeui.bundle.js`
- `transaction_workspace.bundle.js`
- `createEdgeApp`
- `EdgeAppShell`
- `EdgePageLayout`
- `EdgePageHeader`
- EdgeSuite loading/error states

## Safety invariants

- No `ignore_permissions` in the transaction workspace backend.
- No manual DB commit.
- No direct Sales Invoice/Stock Entry insert/save/submit from the workspace backend.
- Explicit native ERPNext full forms remain available as advanced fallbacks.
- Submitted ERPNext accounting/stock documents are never mutated by this feature.

## Manual QA

### Online POSNext

1. Select an Operating Company and Branch.
2. Confirm the Branch Setup POS Profile is shown.
3. Open Transaction Workspace.
4. Start POS while online.
5. Verify compatible active POSNext shift launches normally.
6. Verify a mismatched Company, Branch or POS Profile is blocked with a clear message.

### Offline POSNext

1. Load/login to the site and POSNext while online so required POS assets/session state are available.
2. Confirm the direct `Start POS` navigation item is visible alongside Transaction Workspace.
3. Disconnect the network.
4. Use direct Start POS and Transaction Workspace Start POS independently where cached.
5. Confirm RetailEdge does not require its server preflight while offline.
6. Create an offline sale using POSNext's supported offline mechanism.
7. Reconnect.
8. Verify POSNext syncs according to its own runtime rules.
9. Verify resulting ERPNext documents retain correct Company/Branch/POS Profile attribution.

### Native ERPNext POS fallback

1. Use a site without POSNext shift DocTypes.
2. Confirm Transaction Workspace reports ERPNext Point of Sale.
3. Verify active POS Opening Entry Company/POS Profile mismatch blocks online launch.
4. Verify compatible native POS launches normally.

### Guided transactions

1. Open guided Sales Invoice, Purchase Invoice and Stock Transfer from Transaction Workspace.
2. Confirm the existing guided-entry components load the same context/defaults as Business Hub.
3. Confirm Open Full Form/native fallback remains available.
4. Confirm Sales Order, Delivery Note, Purchase Order and Purchase Receipt continue to open native ERPNext forms.
