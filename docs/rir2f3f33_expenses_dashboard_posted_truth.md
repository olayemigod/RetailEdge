# RIR2F3F33 — Expenses Dashboard Posted-Truth Consolidation

## Goal

Align Expenses Dashboard with the consolidated posted-accounting truth already owned by Expense Register.

The dashboard must not maintain or recreate a separate financial expense dataset. Current period, previous period, MTD, calendar YTD, budget actuals, breakdowns and recent rows all inherit the same Company/Branch permissions and posted-truth rules as Expense Register.

## Single financial authority

Expense Register remains the single financial row authority.

For dashboard financial reads, all existing consumers explicitly request:

- `view_mode = consolidated`;
- `include_unposted_cashier_expenses = 0`.

This applies to:

- selected/current period;
- previous equal-length comparison period;
- month-to-date context;
- calendar-year-to-date context;
- submitted ERPNext Budget actual-spend comparison;
- dashboard export composition.

No new dashboard query engine is introduced.

## Included financial sources

The dashboard therefore inherits the consolidated Expense Register source contract, including:

- posted Cashier / POS expenses;
- posted Business Expenses;
- Business Expense Reversal rows;
- permitted posted Purchase Invoice expense-account lines;
- permitted posted Expense Claim expense-account lines when installed;
- permitted generic Journal Entry expense-account lines.

Sales/POS COGS and stock valuation entries remain outside the allowed accounting source set.

Unposted Cashier Expenses remain operational exposure and are excluded from dashboard financial actuals.

## Reversal semantics

Business Expense Reversal is a negative financial row.

The original Business Expense remains positive and its reversal remains negative. Dashboard totals, trend comparisons, category/branch/account breakdowns, MTD/YTD values and budget actuals therefore use net posted spend rather than silently retaining a reversed expense as positive spend.

The dashboard does not independently inspect or reconstruct reversal accounting.

## Company and Branch scope

Existing Dashboard Capability checks remain in force.

Expense Register then remains authoritative for row-level Company/Branch scope:

- explicit Branch must be permitted;
- restricted single/multi-Branch readers see only their allowed population;
- restricted zero-Branch users fail closed;
- unrestricted blank-Branch reads retain Company-wide behavior.

Requesting the consolidated financial mode does not bypass permissions. Users without consolidated Expense Register eligibility fail closed through the existing register authority.

## Account-context breakdowns

Before F3F33, Expenses Dashboard attempted to re-read `RetailEdge Cashier Expense` using row names returned by Expense Register.

That assumption is invalid after consolidation because posted-truth rows use source-aware synthetic identifiers such as Cashier Expense, Business Expense, Business Expense Reversal and GL rows.

F3F33 removes that secondary Cashier Expense lookup.

When the current user has Account read permission, funding-source, Expense Account and Cost Centre breakdowns use the already-scoped account fields carried by the consolidated Expense Register rows.

Rows without a value for the selected account dimension are omitted from that specific breakdown rather than grouped into a misleading “Unspecified” bucket.

## Cashier breakdown

Cashier is meaningful only for rows that actually belong to a cashier context.

Business Expense, supplier, employee and generic accounting rows must not appear as an “Unspecified cashier” population.

The Cashier breakdown therefore includes only rows with a non-empty Cashier value.

## Recent-expense drilldown

Recent Expenses is now source-aware.

- `RetailEdge Business Expense` rows, including Business Expense Reversal rows whose source remains the Business Expense, route back to the EdgeSuite **Business Expenses** owner.
- `Purchase Invoice` rows route to the EdgeSuite **Purchase Register** when that Page is present.
- Other accounting sources may open their native document only when final Business Hub context grants `can_use_native_desk`.
- Normal EdgeSuite users are not sent to the raw Cashier Expense form.

This is navigation containment only. It does not change underlying document permissions.

## Shared status metadata

Expense Register context now includes **Reversed** in its shared status list so F3F32 reversal state is available consistently to dashboard/register consumers.

The raw active Frappe Workflow state is not treated as financial status truth.

## Dashboard shell and presentation

The existing Expenses Dashboard shell remains unchanged:

- Spend Trend;
- MTD & Calendar YTD;
- Budget & Burn Rate;
- Attention Required;
- breakdown sections;
- Recent Expenses;
- existing export/print actions.

F3F33 is data-authority and drilldown parity, not a visual redesign.

Route promotion remains unchanged. Expense Overview is not promoted into normal navigation by this slice.

## Budget semantics

ERPNext Budget remains the target authority.

F3F33 only changes the actual-spend input to use consolidated posted truth.

Budget enforcement itself is unchanged. RetailEdge still does not infer budget compliance when no reliable submitted budget target exists.

Reversals naturally reduce actual spend because they enter the canonical financial dataset as negative rows.

## Export and period context

Dashboard export continues through the existing Dashboard Files service.

The dashboard export builder calls the same dashboard, budget and period-context services. Because those services are now pinned to consolidated posted truth, screen and export remain aligned.

MTD and YTD retain the existing calendar/time-basis rules.

## Backward compatibility and migration

No schema change is required for F3F33.

The Reversed field values were introduced by F3F32; F3F33 only exposes that existing state consistently through Expense Register metadata.

Existing dashboard routes, capability settings, export/print settings and budget configuration remain unchanged.

## Safety rules

F3F33 does not:

- create or mutate accounting documents;
- modify Business Expense posting/reversal;
- change Cashier Expense workflow/posting;
- include unposted Cashier Expenses in financial dashboard actuals;
- create a second expense ledger;
- add direct SQL to the Expenses Dashboard;
- bypass Company/Branch/DocType permissions;
- promote the dashboard route;
- redesign dashboard visual composition.

## Tests required

Focused contract coverage verifies:

- selected/current period forces consolidated posted truth;
- previous-period comparison inherits that same filter;
- MTD/YTD force consolidated posted truth;
- budget actuals force consolidated posted truth;
- unposted Cashier Expenses remain disabled;
- Account context reuses canonical rows instead of re-reading Cashier Expense;
- blank Cashier/account dimensions are excluded from their specific breakdowns;
- dashboard metadata identifies consolidated posted truth;
- Reversed is present in shared Expense Register status metadata;
- recent drilldown is source-aware;
- Business Expense routes to EdgeSuite Business Expenses;
- Purchase Invoice routes to EdgeSuite Purchase Register where present;
- native fallback remains gated by `can_use_native_desk`;
- no hard-coded raw Cashier Expense form route remains;
- existing dashboard shell/navigation-promotion contract remains unchanged.

The four governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. posted Cashier Expense contributes to dashboard financial totals;
2. unposted Cashier Expense does not contribute;
3. posted Business Expense contributes;
4. Business Expense Reversal reduces net spend;
5. original + full reversal net to zero for the same amount;
6. current/previous trend uses the same posted truth;
7. MTD/YTD match equivalent Expense Register filters;
8. Budget actual spend matches equivalent Expense Register filters;
9. Business Expense recent row opens Business Expenses in EdgeSuite;
10. Business Expense Reversal recent row opens the source Business Expense;
11. Purchase Invoice recent row opens Purchase Register when available;
12. normal EdgeSuite user is not routed to a raw Cashier Expense form;
13. native-capable user may open other accounting source documents subject to normal permissions;
14. restricted Branch users see only permitted data;
15. zero-Branch restricted users fail closed.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope / next boundary

F3F33 does not promote Expense Overview or begin a wider dashboard/reporting redesign.

Any later promotion should occur only after the consolidated RIR2E browser/persona acceptance confirms the posted-truth dashboard and drilldowns.
