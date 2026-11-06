# NEOTEX frontend runtime convergence — 6 November 2026

## Production evidence

- RetailEdge PR #243 is served on NEOTEX (`retailedge_business_hub.bundle.RPHRGBEQ.js`; code marker present).
- The Frappe manifest and HTTP 200 responses resolve `edgesuite_ui.bundle.js` (`LBNBGUUL`), Business Hub (`RPHRGBEQ`), Professional Selling (`RAS7WQDT`), and `edgeui.bundle.css`.
- `window.EdgeSuiteUI.version` is 1.1.0, its Vue version is 3.5.45, `createEdgeApp` exists and shared shell components are registered.
- The browser still contains at least two raw/unresolved EdgeSuite custom elements and Professional Selling crashes reading `null.refs`.
- The production product bundles contain `__v_isVNode` signatures. This is evidence of Vue code patterns, not by itself proof that two Vue module instances execute.

## Two distinct defects and release gates

### A. Collision-safe runtime asset names — corrected on the loader-convergence branch

PR #242 changed only Business Hub, Product Menu and Professional Selling. Most other RetailEdge page controllers and the shell-context bootstrap still requested legacy `edgeui.bundle.js`, whose manifest key may collide with CoreEdge.

All RetailEdge-owned page controllers that requested the legacy name and the shell bootstrap now request `edgesuite_ui.bundle.js`, while preserving their product bundle names and existing business logic.

A source-level regression checks every standard page loader. Existing page contract tests are reconciled. CI must pass before merging.

### B. Vue singleton rendering — still blocked pending proof and implementation

`tsconfig.json` already points `vue` to EdgeSuite UI's `vue-bridge.js`. The bridge explicitly re-exports the Vue instance owned by `window.EdgeSuiteUI.Vue`. Frappe v16 esbuild compiles standalone product entry points; source-only alias assertions do **not** establish that compiler-generated Vue SFC imports resolve to the bridge.

The read-only build-artifact audit reports whether compiled JS contains the bridge's unique error string and Vue runtime signatures. These checks inform diagnosis but are not substitutes for actual browser tests.

Before treating NEOTEX fixed:

1. Inspect built esbuild inputs/metafiles and product SFC render helper imports; demonstrate that the same Vue module instance services the host renderer and the product/Suite components.
2. Correct the build-level `vue` module resolution at its source; do not mask the exception or add page-specific rebinding workarounds.
3. Run authenticated browser tests on **built** EdgeSuite and RetailEdge assets that mount a component tree with nested shared components and template `ref` bindings, asserting no unresolved custom elements or `null.refs` errors.
4. Verify representative sales, POS, purchasing, inventory, banking, reporting, settings, navigation, and light/dark-mode pages.
5. Complete exact-head CI and NEOTEX hosted deployment acceptance; retain no financial/schema/permission changes.

**Release status:** asset-name convergence may be merged after its independent tests, but it does not close issue #244; browser runtime acceptance remains blocked.
