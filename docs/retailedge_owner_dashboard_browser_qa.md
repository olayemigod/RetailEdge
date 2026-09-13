# RetailEdge Owner Dashboard Browser QA

Status: **Required before navigation promotion**

Preview route: `/app/owner-dashboard`

The Owner Dashboard may be developed and validated automatically while this QA is deferred, but it must remain outside normal RetailEdge navigation until the checks below are completed on a real RetailEdge site.

## Preconditions

- Pull the current PR #23 head into the local RetailEdge bench.
- Run `bench --site retail.local migrate` and rebuild assets as required.
- Use a company with realistic submitted sales, expenses, cash/bank movement, receivables, payables, stock and branch data.
- Test at least one management user with broad access and one branch-restricted user.
- Test one user for whom RetailEdge cost-price visibility is restricted.

## QA checklist

### 1. Shell and layout

- Open `/app/owner-dashboard` directly.
- EdgeSuite App Shell is the only visible navigation shell; no competing native sidebar remains.
- Page loads without console errors or missing EdgeSuite components.
- Desktop, tablet and mobile layouts remain usable without clipped cards or controls.

### 2. Scope and filters

- Company and branch context reflect the signed-in user's permitted/default scope.
- Selected From/To dates refresh only period-based sections.
- Sales, Expenses, Cash Movement and Branch Performance are labelled **Selected Period**.
- Receivables, Payables and Stock Position are labelled **Current Position** and do not imply historical reconstruction from the selected dates.
- A branch-restricted user cannot reveal another branch by URL/request manipulation.

### 3. KPI parity

Compare each headline card with its underlying RetailEdge report using the same scope:

- Sales = Sales Invoice Register `Net Invoiced`.
- Expenses = Expense Register `Total Expenses`.
- Receivables = Customer Receivables `Total Receivables`.
- Payables = Supplier Payables `Total Payables`.
- Stock Value appears only when the user is permitted to see RetailEdge cost/valuation information.

No dashboard-only business calculation should differ from the source report.

### 4. Attention Required

Verify that an attention item appears only when the corresponding source summary metric is greater than zero:

- Expense Posting Blocked.
- Expenses Submitted for Review.
- Receivables Overdue / Over 90 Days.
- Payables Overdue / Over 90 Days.
- Negative Stock.
- Out of Stock.
- Fully Reserved stock.

Click each visible attention item and confirm it opens the correct detailed RetailEdge page.

### 5. Permission matrix

- A user without Owner Dashboard view capability cannot load dashboard data directly through the API.
- A user without access to a source report sees that section as restricted and receives no source figures.
- Branch permissions remain authoritative in every underlying section.
- A cost-restricted user receives no Stock Value or other hidden valuation information in the page, API response, export or print output.

### 6. Drill-through

Open every available functional section and confirm routing to:

- Sales Invoice Register.
- Expense Register.
- Cash Movement.
- Customer Receivables.
- Supplier Payables.
- Stock Position.
- Branch Performance.

The detailed pages remain the authoritative investigation surfaces.

### 7. Export / print

Test CSV, XLSX and Print/PDF through the shared EdgeSuite dashboard export controls.

- Export respects dashboard capability permissions.
- Export contains only permitted sections.
- Time Basis is present so Current Position metrics cannot be mistaken for selected-period balances.
- Filter metadata is correct.
- No hidden cost/valuation figure leaks into restricted-user exports.

## Promotion decision

Promote Owner Dashboard into RetailEdge Home/Insights navigation only when:

1. automated CI and Linters are green on the promotion head;
2. the checks above have been completed without unresolved parity, permission, layout or export defects;
3. any native/detail report fallbacks remain available.

Until then `/app/owner-dashboard` remains a preview route only.
