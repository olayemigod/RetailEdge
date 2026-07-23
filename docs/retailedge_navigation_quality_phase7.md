# RetailEdge Navigation Quality — Phase 7

## Business goal

Make RetailEdge navigation simpler, truthful and easier to scan without changing any operational, accounting, reconciliation or stock workflow.

## Problems corrected

The source workspace and sidebar contained several links to the same target under different labels and sections.

Examples included:

- `Reconciliation Handoff` and `Reconciliation Handoff Report`;
- `Bank Transaction Matching` and `Bank Transaction Matching Report`;
- `Payment Statement Import` and `Payment Statement Import Register`;
- `Reconciliation Readiness Review`, `Reconciliation Readiness`, and `Bank Match Integrity Check`;
- `Invoice Payment Audit` and `Sales Invoice Verification Sync`;
- `Reconciliation Handoff` and the misleading `Failed Reconciliation Repair` label.

The setup navigation also exposed `RetailEdge Branch Profile User`, which is a child-table DocType and should be managed through its parent Branch Profile rather than opened as a normal setup screen.

## Navigation policy

RetailEdge now normalizes workspace and sidebar navigation by the real target:

```text
(link_type, link_to)
```

The first workflow-appropriate occurrence wins. Later aliases to the same target are removed.

Because the navigation order is workflow-first:

- operational links remain under Operations;
- reviews and readiness reports remain under Review & Approvals;
- unique management reports remain under Reports & Analytics;
- native accounting documents remain under Accounting / Ledger Bridge;
- setup masters remain under Setup / Configuration;
- unique technical diagnostics remain under Admin / Maintenance.

Sections with no remaining links are removed.

## Workspace and native sidebar

`workspace_sync.py` now normalizes the source-controlled workspace and sidebar data before saving the Frappe Workspace and Workspace Sidebar documents.

This means the policy survives migrate and layout synchronization without manually maintaining hundreds of generated JSON lines.

The existing source JSON remains the discovery input, but duplicate aliases and child-table targets are removed before runtime documents are saved.

## EdgeSuite product menu

The RetailEdge product menu applies the same target-based deduplication defensively.

This helps older sites whose Workspace Sidebar has not yet been synchronized.

The menu also now uses metadata for the actual section labels:

- Operations
- Review & Approvals
- Reports & Analytics
- Accounting / Ledger Bridge
- Setup / Configuration
- Admin / Maintenance

Descriptions were rewritten to describe what each screen actually does. In particular, read-only reconciliation reports no longer imply that they repair or execute reconciliation.

## Hidden navigation targets

The following target is intentionally excluded from normal navigation:

- `RetailEdge Branch Profile User`

Its records remain available through the Branch Profile child table and backend logic. No DocType is deleted or renamed.

## Safety boundaries

This phase does not:

- change DocType permissions;
- delete any document;
- change accounting or stock data;
- create Payment Entries or Journal Entries;
- reconcile Bank Transactions;
- submit or cancel operational documents;
- change report calculations;
- add a migration patch or schema field.

The existing workspace synchronization still writes only the Workspace and Workspace Sidebar configuration documents.

## Files changed

- `retailedge/workspace_navigation.py`
- `retailedge/workspace_sync.py`
- `retailedge/public/js/retailedge_product_menu.js`
- focused navigation-quality tests
- this implementation note

The large generated workspace and sidebar JSON files are not manually rewritten.

## Tests

Regression coverage verifies:

1. Target identity ignores misleading alias labels.
2. The first occurrence of a target is kept.
3. Later duplicate aliases are removed.
4. Empty sections are removed.
5. `RetailEdge Branch Profile User` is hidden.
6. Actual source workspace and sidebar data normalize to unique targets.
7. The product menu uses the correct section names and defensive deduplication.
8. No business-document write or reconciliation action is introduced.

## Manual QA gate

After clean CI, validate:

1. Native RetailEdge workspace cards.
2. Native Frappe sidebar.
3. EdgeSuite product menu.
4. Review and report placement.
5. Setup workspace discovery.
6. Administrator and restricted-role visibility.
7. No duplicate Bank Matching, Readiness, Handoff, Invoice Audit or Payment Import links.
8. No direct Branch Profile User menu item.
9. Mobile product-menu sections.
10. Navigation after `sync_retailedge_workspace_layout`.

## CI dependency

The RetailEdge repository still requires `EDGESUITE_UI_TOKEN` with read-only Contents access to the private `olayemigod/processedge-edge-suite-ui` repository for full build, migration and Frappe test execution.
