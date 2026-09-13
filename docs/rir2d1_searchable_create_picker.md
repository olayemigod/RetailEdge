# RetailEdge RIR2D1 — Searchable Create picker recovery

## Checkpoint

- Authoritative PR: #55
- Authoritative branch: `qa/retailedge-reconciled-20260902`
- Starting head: `7806eaeae237a5819b18af75f5f4bac7f1de7418`
- Scope: restore search inside the Business Hub Create popup only.
- Reporting: remains blocked.
- Manual browser/persona QA remains required after reconciliation automation is frozen.

## Finding

The current Business Hub receives permission-approved `quick_actions` from the server and renders them in the Create popup, but the popup itself had no search control. The existing `retailedge_guided_create_menu.css` already contained complete styles for a guided-create search field, result count and no-match state, so the presentation contract had been prepared without an active runtime owner.

## Recovery decision

RIR2D1 adds a small Business Hub lifecycle helper that enhances only the rendered `.create-picker-list` while the Business Hub app is mounted. The helper:

- adds a focused `type="search"` control using the existing guided-create CSS classes;
- searches the text already rendered for each permitted Create action;
- hides only non-matching rendered action buttons;
- shows a live result count and a no-match state;
- lets Escape clear an active query before the modal-level Escape closes the dialog;
- disconnects its MutationObserver and removes its presentation state when the Business Hub app unmounts.

Because EdgeSuite `EdgeModal` portals open dialogs to `document.body`, the helper observes the document only for the lifetime of the Business Hub app rather than assuming the modal remains under the original mount target.

## Security and behaviour boundary

This is a presentation-only recovery. Search receives no new server data and does not change creation permissions. `RetailEdgeBusinessHub.vue` remains the owner of `quickActions` and `runQuickAction()`; existing guided dialogs and native fallback rules are untouched.

RIR2D1 does not change:

- server APIs or permission checks;
- Company/Branch scope;
- Branch Assignment authority;
- ERPNext document creation or validation;
- accounting, stock or payment posting semantics;
- native Desk exposure;
- route composition;
- keyboard-command ownership;
- Banking/Bank Matching behaviour;
- the reconciled QA branch structure.

Manual browser/persona QA remains required for focus, filtering, keyboard interaction, mobile layout, light/dark theme and all permitted persona combinations.
