# RetailEdge EdgeSuite UI Programme

## Decision record — 5 August 2026

RetailEdge will continue from the completed Stock Movement History baseline into a phased EdgeSuite UI migration and business-product redesign.

RetailEdge UI migration targets the independent `processedge-edge-suite-ui` Frappe app (`edgesuite_ui`). It must not import UI components, Vue files, bundles, or browser runtime objects from CoreEdge. The canonical consumer contract is:

- Frappe app: `edgesuite_ui`
- Browser asset: `edgeui.bundle.js`
- Browser runtime: `window.EdgeSuiteUI`
- Product apps retain all business rules, permissions, APIs, and document writes

The temporary `window.EdgeUI` browser alias is not valid for new RetailEdge migration work. New product pages must use `window.EdgeSuiteUI`, while the shared asset continues to use its established Frappe bundle name, `edgeui.bundle.js`.

The **RetailEdge waffle product menu is active**. Only cross-product switching is suspended. The waffle currently provides professional, permission-aware navigation inside RetailEdge and does not call CoreEdge or switch to another EdgeSuite product.

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

The RetailEdge waffle is part of Navigate and is active in the current phase. Cross-product switching remains a later Navigate capability.

## Current implementation slice

The first EdgeSuite slice introduces:

- A permission-aware RetailEdge programme and navigation registry.
- A new `RetailEdge Business Hub` EdgeSuite UI page.
- A RetailEdge waffle product menu that works across native Desk and EdgeSuite shell pages.
- The five programme experiences displayed as one coherent product direction.
- Quick actions that create existing native ERPNext/RetailEdge documents.
- Professional business navigation groups.
- An explicit API feature flag keeping cross-product switching disabled.
- Regression tests for programme order, menu structure, standalone runtime loading, waffle registration, and product-switcher suspension.

The quick actions are intentionally safe native fallbacks. They do not yet claim to be guided RetailEdge forms.

## Browser boot contract

- Register the standard Frappe Page controller explicitly from RetailEdge Desk assets.
- Load the shared runtime from `edgeui.bundle.js` only when it is not already present.
- Load `retailedge_product_menu.bundle.js` at Desk startup and register the permission-aware RetailEdge waffle.
- Load the product-owned `retailedge_business_hub.bundle.js` lazily through Frappe's Promise-based asset API.
- Support the older callback completion path during migration.
- Retry Business Hub mounting from `on_page_show` when the first route lifecycle misses or fails before creating the Vue app.
- Refresh and remount the waffle on toolbar, route, sidebar, and desktop lifecycle changes.
- Display a visible Business Hub failure state rather than leaving an empty native Frappe shell.

## Waffle versus product switching

The two behaviours are deliberately separate:

- **Waffle product menu:** enabled now. It opens RetailEdge sections such as Sales, Purchases, Inventory, Cash & Banking, Expenses, Reports & Insights, Setup, and restricted Administration.
- **Cross-product switching:** suspended. The current waffle does not switch from RetailEdge to VetEdge, EduEdge, CoreEdge, or another product.

## Local verification

```bash
bench build --app edgesuite_ui
bench build --app retailedge
bench --site <site-name> migrate
bench --site <site-name> clear-cache
bench clear-website-cache
grep -E 'edgeui\.bundle|retailedge_(business_hub|product_menu)\.bundle' sites/assets/assets.json
```

The asset manifest must contain all three bundles before browser QA proceeds:

- `edgeui.bundle.js`
- `retailedge_business_hub.bundle.js`
- `retailedge_product_menu.bundle.js`

## Next slices

### Slice 2 — Navigation migration

- Complete the professional workspace and sidebar classification.
- Apply role-focused visibility without weakening ERPNext permissions.
- Remove ordinary-user exposure to administration and unused EdgePay surfaces.
- Keep the waffle registry aligned with the workspace navigation registry.

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
- The RetailEdge waffle may show only permission-approved RetailEdge destinations.
- Cross-product switching remains disabled until it is intentionally resumed.
- No private CoreEdge frontend imports are permitted.
