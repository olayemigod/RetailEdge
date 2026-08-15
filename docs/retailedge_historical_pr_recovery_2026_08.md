# RetailEdge Historical PR Recovery Ledger — August 2026

## Purpose

This ledger prevents useful work from being lost while RetailEdge retires the older stacked EdgeSuite UI migration branches and continues on the current Business Hub programme.

The canonical implementation line is PR #16 / `feat/retailedge-edgesuite-ui-foundation`, built from the preserved Stock Movement History checkpoint. Historical PR implementations must not be merged wholesale because they target older EdgeSuite runtime contracts and a different migration sequence.

A historical PR may be closed only when its disposition is recorded here as one of:

- **Recovered** — required behaviour has been ported to the current branch.
- **Superseded** — the current programme provides a newer implementation of the same intent.
- **Retained requirement** — useful business behaviour remains required, but must be rebuilt against the current runtime in the stated slice.
- **Intentionally deferred** — the behaviour is deliberately not active in the current product direction.

## Recovery map

### PR #3 — EdgeSuite consumer foundation and Home

**Disposition: Superseded.**

The current Business Hub foundation replaces the old RetailEdge Home/product-shell implementation. Preserve the intent: permission-aware RetailEdge identity, safe native fallback, no CoreEdge frontend dependency, role-aware navigation and explicit visible asset-load failure.

### PR #4 — shared EdgeSuite report adapter

**Disposition: Retained requirement.**

Do not merge the historical adapter. Rebuild the useful read-only presentation behaviour in the current **Understand** programme:

- Branch Performance Summary;
- Cashier Expense Review;
- Daily Sales Audit Register;
- native Query Report filters, table links, export, print and refresh remain authoritative;
- EdgeSuite presentation must fail open to native report behaviour;
- no report surface may create accounting, stock or reconciliation writes.

Target: Slice 5 Essential Reports / Slice 6 Dashboards as appropriate.

### PR #5 — Salesperson Performance Dashboard shared runtime migration

**Disposition: Retained requirement.**

The Salesperson Performance Dashboard remains a required RetailEdge insight surface. Preserve these requirements when normalized to the current EdgeSuite runtime:

- permission-aware lazy Salesperson, Customer, Item and Branch links;
- Company and Branch server scope;
- Branch → Customer/Item and Customer → Item cascade clearing;
- proportional Sales Team allocation remains authoritative;
- pagination and native document links;
- no Sales Invoice/Sales Team/payment/accounting mutation.

### PR #6 — EdgeSuite setup document workspace

**Disposition: Retained requirement.**

Preserve a guided RetailEdge-owned setup surface for Branch Profile and RetailEdge Settings, using an explicit resource allowlist, native controllers/permissions, optimistic timestamp protection, smart Link filtering and native form fallback. Do not expose generic arbitrary-DocType writes.

Target: Slice 2 Navigation / Slice 3 Guided Entry framework.

### PR #7 — master setup resources

**Disposition: Retained requirement.**

Preserve Expense Category and Statement Mapping Template management with Company-aware Account/Cost Center validation, exclusion of group accounts and normal Frappe permissions. Rebuild in the current setup framework rather than merging the old workspace implementation.

### PR #8 — control reports

**Disposition: Retained requirement.**

Preserve read-only EdgeSuite intelligence for:

- Invoice Payment Audit;
- Cash Shift Verification;
- Unmatched Bank Transactions.

Native report queries and accounting truth remain authoritative. No Bank Match Review, reconciliation, Payment Entry or Journal Entry action belongs in the read-only report adapter.

### PR #9 — reconciliation oversight reports

**Disposition: Retained requirement.**

Preserve read-only oversight for:

- Bank Match Reconciliation Readiness;
- Reconciliation Handoff;
- Unmatched Bank Payment Events.

The rebuilt surfaces may explain blockers and readiness but must not confirm matches or reconcile transactions automatically.

### PR #10 — POS Closing Variance intelligence

**Disposition: Retained requirement.**

Preserve the read-only management interpretation of POS Closing Variance vs Expenses, including shortage, expense, unmatched-shortage and exception guidance while keeping the native tree report, filters and accounting/stock truth unchanged.

### PR #11 — prevent branch variance cancellation

**Disposition: Recovered.**

The current branch now calculates the management headline as **Absolute Audit Variance** using the sum of `abs(audit_variance)` across branch rows. The row-level Audit Variance remains signed so shortages and overages remain distinguishable.

Recovery commits on the current branch:

- `36a367ab80dc1c5d465a0abc46c53b7e521b1f88` — calculation correction;
- `ac17fdc11c496a9979dbeff8c165e36ba2914c43` — regression coverage.

### PR #12 — navigation simplification and deduplication

**Disposition: Retained requirement.**

Carry these rules into Slice 2 Navigation migration:

- identify duplicate navigation by actual destination, not display label;
- keep the first workflow-appropriate occurrence;
- hide child-table DocTypes such as RetailEdge Branch Profile User from ordinary navigation;
- remove empty sections and recalculate section counts;
- preserve optional POSNext Opening/Closing Shift links only when their target DocTypes exist;
- apply the same destination deduplication to native workspace/sidebar and the RetailEdge waffle.

### PR #13 — Stock Movement History

**Disposition: Recovered / baseline.**

The Stock Movement History branch is the preserved pre-EdgeSuite checkpoint and is an ancestor of the current PR #16 line. It has already been closed as superseded by the current branch.

### PR #14 — cross-product Product App switcher

**Disposition: Intentionally deferred.**

Do not port the historical cross-product switching implementation now. The current programme explicitly keeps the RetailEdge waffle enabled while **cross-product switching is suspended**. When switching is resumed, implement it against the then-current shared EdgeSuite Product App contract rather than recovering this old branch.

## Current QA boundary

Browser QA for the current RetailEdge foundation should validate only behaviour already implemented in PR #16 plus recovered correctness fixes. Retained requirements above are not to be falsely treated as completed merely because their historical PRs existed.

Future implementation slices must reference this ledger so no retained report, setup, navigation or dashboard requirement disappears during the redesigned rollout.
