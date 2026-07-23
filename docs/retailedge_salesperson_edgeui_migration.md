# RetailEdge Salesperson Performance EdgeSuite Migration

## Branch and dependency

This phase is implemented on `agent/retailedge-edgeui-salesperson-dashboard` and is stacked on `agent/retailedge-edgeui-report-adapter`.

It requires the local `edgesuite_ui` app and the shared EdgeSuite UI 0.5+ runtime. RetailEdge CI also requires the repository secret `EDGESUITE_UI_TOKEN` with read access to `olayemigod/processedge-edge-suite-ui`.

## Business goal

Provide a fast, branch-safe salesperson performance dashboard that explains proportional Sales Team allocation without replacing ERPNext invoices, salesperson records, customers, items or accounting truth.

## Implemented changes

- Removed local copies of EdgeAppShell, EdgePageLayout, EdgePageHeader, EdgeFilterBar, EdgeStatCard, EdgeStatusBadge, EdgeLoadingState, EdgeErrorState and EdgeEmptyState.
- Removed the compatibility runtime that rewrote `window.EdgeUI`.
- Mounted the page through the shared RetailEdge Vue app factory and `runtime.install(app)`.
- Added the shared EdgeBranchContextSwitcher.
- Replaced preloaded Salesperson options and free-text Customer/Item inputs with shared EdgeLinkField controls.
- Added a permission-aware server search capped at 30 results.
- Kept only permitted branches, enabled salespeople, active readable customers and active sales items in search results.
- Added company scoping to all Sales Invoice aggregation queries.
- Preserved branch restrictions and added backend validation for manually forged Link filters.
- Added stale-request protection so slower responses cannot overwrite newer filter results.
- Preserved proportional Sales Team allocation, pagination and direct links to Sales Person, Sales Invoice and Customer records.

## Cascade behaviour

- Changing Branch clears Customer and Item because those choices may no longer be useful in the new reporting context.
- Changing Customer clears Item before loading the next result set.
- Link fields search lazily instead of loading every master record into the browser.
- Leaving Branch blank means all branches the current user is permitted to access, not unrestricted company-wide access.

## Safety boundaries

This phase is read-only. It does not submit, save, cancel or mutate:

- Sales Invoice;
- Sales Team rows;
- Payment Entry;
- Customer;
- Item;
- Sales Person;
- GL Entry;
- stock or POS shift documents.

ERPNext Sales Invoice and Sales Team records remain the calculation source of truth.

## Automated validation gate

The changed-file linter, Semgrep and dependency audit can run without a full bench. Clean Frappe installation, EdgeSuite/RetailEdge asset builds, migration and Frappe tests remain blocked until `EDGESUITE_UI_TOKEN` is configured in the RetailEdge repository.

## Manual QA gate

Manual QA is deferred. Before merge, verify:

1. Shared EdgeSuite shell and controls render without local fallback components.
2. Company and branch scope match the logged-in user.
3. Branch, Salesperson, Customer and Item searches respect permissions and active status.
4. Branch and Customer cascade clearing behaves as documented.
5. Proportional totals reconcile to submitted Sales Invoice Sales Team percentages.
6. Direct document links, pagination and date presets work.
7. Full History clears dates and manual date edits switch to Custom Period.
8. Mobile table scrolling and filter layout remain usable.
9. Missing or outdated EdgeSuite UI produces the plain loader failure block rather than a blank page.
