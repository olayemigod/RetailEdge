# EdgeSuite Product App Switcher — Implementation Status

Date: 25 July 2026

## Shared runtime

- EdgeSuite UI PR #12 uses `edgesuite_ui.bundle.js` as the canonical global runtime asset.
- The historical `edgeui.bundle.js` entry point remains temporarily as a compatibility alias only.
- Shared runtime CI is passing.

## Consumer status

| Consumer | Branch / PR | Status |
|---|---|---|
| RetailEdge | `agent/retailedge-product-app-switcher` / PR #14 | CI and linters passing |
| Veterinary | `agent/vetedge-product-app-switcher` / PR #22 | Canonical loaders implemented; final full CI running |
| EduEdge | `agent/eduedge-integrated-foundation` / PR #9 | Canonical loader sweep and pure contract CI passing |
| EdgePay | `agent/edgepay-edgesuite-product-surface` / PR #1 | Dependency install, build and server tests passing; changed-file formatting validation running |
| CoreEdge Platform | `agent/coreedge-edgesuite-consumer` / PR #14 | Restricted consumer implemented; dependency install/build passing; final tests and formatting validation running |

## Product visibility rules

- Installation alone does not make a product available.
- Each product supplies a server-authoritative availability provider.
- RetailEdge, Veterinary, EduEdge and EdgePay are operational products.
- CoreEdge Platform is restricted to explicit platform administration roles.
- EdgePay preserves internal app identity `edgepayv1` while registering stable product key `edgepay`.
- Only one active product menu and one waffle should render at a time.

## Safety preserved

- No submitted Sales Invoice, Payment Entry, Journal Entry, Stock Entry or other accounting document is mutated.
- No Veterinary clinical document is changed by the switcher work.
- No EduEdge academic, CBT or fee record is changed by the runtime migration.
- EdgePay provider credentials, live-call gates and webhook secrets remain outside the normal user product menu.
- CoreEdge legacy UI source remains temporarily available for rollback but is not the active shared runtime.

## Remaining acceptance gate

1. Complete VetEdge, EdgePay and CoreEdge automated validation.
2. Build and migrate the final branch set on controlled sites.
3. Clear caches and restart the bench.
4. Test authorised and unauthorised users.
5. Confirm only server-returned products appear.
6. Confirm switching opens the selected product Home and refreshes its menu.
7. Confirm single-product sites hide the selector.
8. Confirm forged unavailable-product switching is rejected.
9. Confirm one Product App selector and one active-product waffle are visible.

Keep all switcher PRs draft until combined browser acceptance is complete.
