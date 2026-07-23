# RetailEdge EdgeSuite POS Closing Variance — Phase 5

## Business goal

Make POS closing variance easier to understand without changing the existing shift, expense, invoice, accounting or stock workflows.

The report should quickly answer:

- How much cash shortage exists?
- How much expense evidence is attached to the shifts?
- How much RetailEdge cashier expense is included?
- How much shortage remains unexplained?
- Which shifts still need review, clarification or branch correction?

## Product and technical layer

- Product app: RetailEdge
- Report: POS Closing Variance vs Expenses
- Shared presentation: EdgeSuite UI Query Report adapter
- Data and accounting authority: the existing report provider and ERPNext documents

## Implementation approach

The server-side report provider is intentionally unchanged.

The existing provider already returns:

- closing summary rows;
- payment variance detail rows;
- ERPNext expense detail rows;
- RetailEdge Cashier Expense detail rows;
- native summary cards.

The report JavaScript now builds presentation metadata from the already-returned closing summary rows and sends it to the shared adapter through `renderSummary`.

This avoids rewriting or duplicating the large report provider while keeping the native server summary as the fallback.

## EdgeSuite surface

The report now displays:

- a Cash Control Intelligence header;
- active date, company, branch, POS Profile, cashier and cost-centre context;
- Total Shortage;
- Total Expenses;
- Total RetailEdge Cashier Expenses;
- Unmatched Shortage;
- current-view status;
- evidence-based recommendations;
- empty-state guidance.

## Recommendations

The presentation layer may recommend review when it detects:

- unmatched cash shortages;
- adjusted cash variance after RetailEdge expenses;
- expenses exceeding recorded shortages;
- pending, draft or clarification-required cashier expenses;
- missing branch attribution on closing summary rows.

These recommendations are derived from report rows only. They do not modify documents.

## Preserved behaviour

The following remain unchanged:

- server-side data provider;
- report filters;
- required date validation;
- tree view;
- parent and child row structure;
- POS Closing Shift links;
- POS Opening Shift links;
- voucher links;
- expense and account evidence;
- native server summary;
- export and print;
- existing permissions and data scope.

## Safety boundaries

This phase does not:

- create or update a RetailEdge Cashier Expense;
- create or update a POS Opening Shift;
- create or update a POS Closing Shift;
- submit or cancel a shift;
- update a Sales Invoice or Payment Entry;
- create a Journal Entry;
- change GL or stock;
- write any database value;
- add a whitelisted action endpoint.

## Files changed

- `pos_closing_variance_vs_expenses.js`
- focused POS variance EdgeSuite test module
- this implementation note

The 700-line Python report provider is not modified.

## Migration and backward compatibility

- No DocType field is added or changed.
- No patch or database migration is introduced.
- Existing report route and name remain stable.
- Existing filters and tree layout remain stable.
- If EdgeSuite UI is unavailable, the existing native report and summary remain available.

## Automated tests required

The focused tests cover:

- existing native summary calculations;
- exclusion of detail rows from headline totals;
- shared adapter attachment;
- client use of existing report rows;
- preservation of tree settings and filters;
- absence of operational and accounting write calls.

Full build, migration and Frappe tests must run after the private EdgeSuite UI dependency can be checked out in CI.

## Manual QA gate

After clean CI, validate:

1. Report loading for one and multiple closing shifts.
2. Company, branch, POS Profile, cashier and cost-centre filters.
3. Include COGS behaviour.
4. Parent and child tree expansion.
5. KPI totals against parent closing rows.
6. Shortage, expense, adjusted variance and unmatched-shortage recommendations.
7. Pending expense and missing-branch guidance.
8. Native links and export/print.
9. Native fallback when EdgeSuite UI is unavailable.
10. Desktop and mobile layouts.

## CI dependency

The RetailEdge repository still requires `EDGESUITE_UI_TOKEN` with read-only Contents access to the private `olayemigod/processedge-edge-suite-ui` repository.

The dependency must not be replaced with copied shared assets, duplicated components or a fake CI-only app.
