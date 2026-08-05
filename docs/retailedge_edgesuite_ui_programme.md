# RetailEdge EdgeSuite UI Programme

## Decision record — 5 August 2026

RetailEdge will continue from the completed Stock Movement History baseline into a phased EdgeSuite UI migration and business-product redesign.

RetailEdge UI migration targets the independent `processedge-edge-suite-ui` Frappe app (`edgesuite_ui`). It must not import UI components, Vue files, bundles, or browser runtime objects from CoreEdge. The canonical consumer contract is:

- Frappe app: `edgesuite_ui`
- Browser asset: `edgeui.bundle.js`
- Browser runtime: `window.EdgeSuiteUI`
- Product apps retain all business rules, permissions, APIs, and document writes

The temporary `window.EdgeUI` browser alias is not valid for new RetailEdge migration work. New product pages must use `window.EdgeSuiteUI`, while the shared asset continues to use its established Frappe bundle name, `edgeui.bundle.js`.

The product switcher and waffle work are suspended. No new product-switcher behaviour is part of the current implementation branch.

## Protected pre-EdgeSuite checkpoint

The exact pre-EdgeSuite commit is:

- Commit: `f6be1b9a005101357fcdca558aeb9890787bfff6`
- Original branch retained: `feat/retailedge-stock-movement-history`
- Archive branch: `archive/retailedge-pre-edgesuite-ui-2026-08-05`
- EdgeSuite implementation branch: `feat/retailedge-edgesuite-ui-foundation`

The archive branch is the preferred long-term installation reference because the implementation branch will continue advancing.

### Fresh installation from the preserved checkpoint

```bash
bench get-app --branch archive/retailedge-pre-edgesuite-ui-2026-08-05 \
  https://github.com/olayemigod/RetailEdge.git
bench --site <site-name> install-app retailedge
bench build --app retailedge
bench --site <site-name> migrate
```

### Existing checkout

```bash
cd ~/frappe-bench/apps/retailedge
git fetch origin
git checkout archive/retailedge-pre-edgesuite-ui-2026-08-05
cd ~/frappe-bench
bench build --app retailedge
bench --site <site-name> migrate
```

Do not move the archive branch during normal development.

## Final programme structure

RetailEdge will deliver five connected experiences:

1. **Navigate** — professional menu, product navigation, and role-aware discovery.
2. **Act** — guided entries and quick business actions.
3. **Operate** — role-focused workspaces, approvals, and exception queues.
4. **Understand** — reports, dashboards, and trusted KPI definitions.
5. **Respond** — alerts, reminders, follow-up actions, and explainable recommendations.

Product switching remains a future Navigate capability but is not active in the current phase.

## Current implementation slice

The first EdgeSuite slice introduces:

- A permission-aware RetailEdge programme and navigation registry.
- A new `RetailEdge Business Hub` EdgeSuite UI page.
- The five programme experiences displayed as one coherent product direction.
- Quick actions that create existing native ERPNext/RetailEdge documents.
- Professional business navigation groups.
- An explicit API feature flag keeping product switching disabled.
- Regression tests for programme order, menu structure, canonical standalone runtime loading, and product-switcher suspension.

The quick actions are intentionally safe native fallbacks. They do not yet claim to be guided RetailEdge forms.

## Browser boot contract

- Register the standard Frappe Page controller explicitly from RetailEdge Desk assets.
- Load the shared runtime from `edgeui.bundle.js` only when it is not already present.
- Load the product-owned `retailedge_business_hub.bundle.js` lazily through Frappe's Promise-based asset API.
- Support the older callback completion path during migration.
- Retry mounting from `on_page_show` when the first route lifecycle misses or fails before creating the Vue app.
- Display a visible failure state rather than leaving an empty native Frappe shell.

## Next slices

### Slice 2 — Navigation migration

- Add the Business Hub to the RetailEdge workspace and sidebar.
- Replace the current technical workspace classification with the approved professional groups.
- Apply role-focused visibility without weakening ERPNext permissions.
- Remove ordinary-user exposure to administration and unused EdgePay surfaces.

### Slice 3 — Guided Entry framework

- Shared step-based entry shell.
- Company, branch, warehouse, party, and account context.
- Cascading filters and backend validation.
- Draft, submit, retry, duplicate prevention, attachments, and full-form escape hatch.

### Slice 4 — First guided entries

- Simple Sales Invoice.
- Receive Customer Payment.
- Pay Supplier.
- Record General Expense.
- Simple Purchase Invoice.
- Simple Stock Transfer.

### Slice 5 — Essential reports

- Sales Invoice Register.
- Item Sales Analysis.
- Stock Movement History EdgeSuite UI presentation.
- Stock Position.
- Cash Movement Statement.
- Expense Register.

### Slice 6 — Dashboards

- Business Overview.
- Branch Operations.
- Cash & Banking.
- Stock Intelligence.
- Expenses & Payables.

### Slice 7 — Respond layer

- Exception alerts.
- Recurring operational responsibilities.
- CoreEdge-delivered email, SMS, WhatsApp, and in-app reminders where appropriate.
- Explainable recommendations linked to source documents.

CoreEdge may provide platform services through APIs, but it is not the RetailEdge frontend component library.

## Safety rules

- Native ERPNext documents remain the accounting and stock truth.
- Submitted accounting documents are never mutated.
- Product apps do not duplicate ledgers, invoices, payments, or stock documents.
- Company, branch, role, and permission rules are enforced on the backend.
- Cost values continue to respect RetailEdge cost-price masking.
- Every dashboard metric must use a documented KPI definition and drill down to evidence.
- Existing bank matching, POS, branch attribution, and reporting behaviour must be preserved.
- New RetailEdge UI pages must use `edgeui.bundle.js` and `window.EdgeSuiteUI` only.
- No private CoreEdge frontend imports are permitted.
