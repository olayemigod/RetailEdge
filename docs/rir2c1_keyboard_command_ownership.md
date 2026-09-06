# RetailEdge RIR2C1 — Keyboard command ownership recovery

## Checkpoint

- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Starting head: `d8a69dffe3562b4b9bb3330cacec4b48f41725c7`
- Scope: recover historical keyboard-command intent without creating duplicate global listeners.
- Reporting: remains blocked.
- Manual browser/persona QA: remains deferred to the consolidated reconciliation QA stage.

## Historical source reviewed

The historical `agent/edgesuite-keyboard-commands` branch contained:

- `bdeacaaa88899946d313e488592ca3ff98dff887` — add shared keyboard commands inside RetailEdge;
- `65d1844328fe5563c662aa229bb22bb92b11442b` — load the RetailEdge keyboard asset globally;
- `981a6e4803373ca00df2376309c15af6ffac3a40` — source-contract tests.

Those commits are classified **SUPERSEDED_SHARED_RUNTIME** for the reconciled product. **Do not cherry-pick** them into PR #55 because the governed EdgeSuite UI 1.1.0 candidate now owns the same cross-product responsibility.

## Current shared ownership

The governed EdgeSuite UI candidate pinned by RetailEdge compatibility CI is `e40ea4d7dc000d17443a0571c1e246b61bfd3e1d`.

It globally loads:

- `edgeui_ctrl_k_guard.js` — Ctrl/Cmd+K opens the current EdgeSuite Product Menu and focuses/selects `.edge-product-menu__search`;
- `edgeui_ctrl_s_guard.js` — Ctrl/Cmd+S saves only the current safe context, refuses submitted Frappe documents, and delegates non-form saves through the shared EdgeSuite command runtime;
- `edgeui/interaction_runtime.js` — owns `registerSaveHandler`, `saveCurrentContext`, and the `edgesuite:save-request` contract.

RetailEdge therefore must not register a second document/window keyboard listener for these commands.

## RetailEdge integration

RetailEdge already registers its permission-aware Product Menu through `retailedge_product_menu.bundle.js`. The first section contains the current `+ Create` action. Selecting it invokes `requestGuidedCreate()`, which opens or routes to the Business Hub guided Create surface without bypassing RetailEdge permissions or EdgeSuite-only restrictions.

Ctrl/Cmd+K is therefore a searchable entry point to the current RetailEdge menu and its `+ Create` action through the shared EdgeSuite product-menu search. RIR2C1 does not claim that the Business Hub Create modal itself has an internal search field; if persona QA requires search inside that modal specifically, that is a separate bounded UX correction and not keyboard-command recovery.

## Safety contract

RIR2C1 makes no RetailEdge production runtime change. It freezes shared ownership through compatibility CI and local source-contract tests.

The shared save command must continue to:

- refuse submitted documents;
- use normal `form.save()` for an active draft Frappe Form;
- use only the shared registered/event save contract for EdgeSuite contexts;
- never use `ignore_permissions`, direct `frappe.db.set_value`, `frappe.client.save`, or docstatus mutation to manufacture saveability.

This slice does not change accounting, stock, payments, Bank Matching, Banking Readiness, Branch Assignment authority, route composition, native-Desk exposure, or the reconciled QA branch structure.
