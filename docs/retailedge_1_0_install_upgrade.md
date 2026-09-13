# RetailEdge 1.0.0 — Installation and Upgrade Notes

## Supported release contract

RetailEdge 1.0.0 targets Frappe / ERPNext v16 and uses ProcessEdge EdgeSuite UI as its required shared frontend runtime.

- RetailEdge app: retailedge
- Release target: 1.0.0
- Required app: edgesuite_ui
- ERPNext: v16
- POSNext: supported where POS workflows are used, but not a hard RetailEdge install dependency
- CoreEdge: not required for the standalone 1.0 deployment contract

Use a staging site first for any production upgrade.

## Fresh installation

1. Provision a Frappe / ERPNext v16 bench and site.
2. Install the governed EdgeSuite UI build before RetailEdge.
3. Install RetailEdge.
4. Build the complete Desk asset graph.
5. Run migrations and clear cache.
6. Sign in as System Manager and complete RetailEdge setup before assigning ordinary operational users.

Typical bench sequence after the apps are present in the bench:

    bench --site <site> install-app edgesuite_ui
    bench --site <site> install-app retailedge
    bench build
    bench --site <site> migrate
    bench --site <site> clear-cache

Do not use an app-only asset build as a substitute for the complete Desk build on a clean deployment.

## Upgrade to 1.0.0

Before changing code:

    bench --site <site> backup --with-files

Then:

1. pin or pull the approved Frappe/ERPNext v16, EdgeSuite UI and RetailEdge release revisions;
2. refresh Python/Node requirements as required by the bench;
3. build the complete Desk assets;
4. run bench --site <site> migrate;
5. clear cache and restart/redeploy the bench;
6. verify Business Hub, Action Centre, Company/Branch scope, users/roles, Banking, Expenses, Stock, Selling and Purchasing before opening the site to users.

Representative sequence:

    bench setup requirements
    bench build
    bench --site <site> migrate
    bench --site <site> clear-cache
    bench restart

On managed hosting, use the provider's normal deployment/restart process instead of bench restart.

## Migration safety

RetailEdge 1.0 keeps ERPNext as the accounting and stock source of truth.

- Patches must remain idempotent.
- Existing submitted Sales Invoices, Purchase Invoices, Payment Entries, Stock Entries and other submitted accounting/stock documents must not be mutated to “fix” history.
- Corrections must use ERPNext-safe replacement, credit/debit, write-off, allocation or new-draft patterns.
- Branch Assignment history remains authoritative once it exists for a restricted RetailEdge user.
- Restricted users with no active Branch assignment fail closed.

The governed upgrade workflow installs a representative pre-MVP baseline, seeds representative data, upgrades to the candidate, migrates twice, and runs the current RetailEdge suite. This gate must be green on the final release head.

## Post-upgrade verification

Verify at minimum:

- Business Hub opens without native sidebar competition or runtime modals;
- Action Centre loads and links to canonical RetailEdge Pages;
- Sales and Purchasing users reach their EdgeSuite workspaces;
- Accounts users reach Banking Readiness and Bank Matching;
- cashier users do not gain Banking access;
- Branch Manager and restricted users see only permitted Branch context;
- one-Branch users resolve safely, multi-Branch users are required to choose where necessary, and restricted-zero users fail closed;
- Stock Position and guided stock context use permitted Branch/Warehouse scope;
- Business Expenses and Cashier Expense remain separate governed flows;
- dark/light mode and narrow/mobile Business Hub remain usable.

## Rollback

If a production deployment fails before business transactions resume:

1. stop user access;
2. restore the pre-upgrade database/files backup;
3. restore the previously approved app revisions;
4. rebuild assets, migrate if required for the restored revisions, clear cache and restart;
5. validate accounting/stock totals before reopening.

Do not manually reverse schema or submitted accounting records as a rollback technique.
