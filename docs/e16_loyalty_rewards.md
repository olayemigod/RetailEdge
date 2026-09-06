# E16 C23 — Loyalty & Rewards Contract

## Business goal

Make ERPNext-native loyalty visible and useful inside RetailEdge Professional Selling without creating a second rewards wallet, ledger, balance calculation, redemption engine, or accounting path.

## Authority

ERPNext v16 remains the sole authority for:

- Customer loyalty-program enrolment;
- Loyalty Program company, dates, tiers, collection factor, conversion factor, expense account and cost centre;
- non-expired available points as of the Sales Invoice posting date;
- Sales Invoice loyalty-redemption validation;
- Loyalty Point Entry creation on Sales Invoice submission;
- earned-point recalculation for returns;
- redemption and award reversal on cancellation;
- the accounting effect of loyalty redemption.

RetailEdge must not insert, update, delete, submit, or cancel a Loyalty Point Entry.

## Product surface

### Pricing & Promotions

Add the native ERPNext `Loyalty Program` DocType to the existing **Pricing & Promotions** navigation group. The target remains a permission-aware native DocType route; RetailEdge does not add a replacement loyalty-program master.

### Professional Selling

Extend only the existing guided **New Invoice** mode in Professional Selling:

1. After a Customer is selected, load a permission-aware loyalty summary for the operating Company and selected posting date.
2. Derive the programme from `Customer.loyalty_program`; the browser may not nominate a different programme.
3. Show only operational fields needed by the seller:
   - programme;
   - current tier, when available;
   - available non-expired points;
   - ERPNext conversion factor;
   - available redemption value in the Company currency;
   - programme validity dates when available.
4. Permit a positive whole-number number of points, no greater than the currently available points, to be requested for redemption.
5. Revalidate the Customer, Company, assigned programme, posting date, current points and requested points server-side when creating the draft.
6. Create the Sales Invoice through the existing guarded draft engine.
7. Set ERPNext's native draft fields `redeem_loyalty_points`, `loyalty_program`, and `loyalty_points`.
8. Let ERPNext validation derive and validate `loyalty_amount`, `loyalty_redemption_account`, and `loyalty_redemption_cost_center`.
9. Return the created draft route and the ERPNext-validated loyalty summary.

The existing no-loyalty guided invoice behaviour must remain unchanged.

## Enrolment boundary

C23 does not auto-enrol Customers and does not call ERPNext's `Sales Invoice.get_loyalty_programs` helper because that helper can write `Customer.loyalty_program` when it finds one programme.

If the Customer has no assigned programme, the guided form reports that no programme is assigned and directs authorised users to the native Customer/Loyalty Program workflow. If the assigned programme belongs to another Company, the flow fails closed.

## Conversion boundary

Quotation → Sales Invoice, Sales Order → Sales Invoice, Delivery Note → Sales Invoice, and Return / Credit Note mappings remain unchanged in C23.

Those paths already create an ERPNext draft and open it in the native form. Loyalty can be reviewed or added there using ERPNext's native workflow. C23 must not introduce a post-creation mutation endpoint merely to duplicate native form behaviour.

## Permission and context rules

- Require native Sales Invoice create permission.
- Require read access to the selected Customer and operating Company.
- Reuse the existing server-authoritative Operating Company/Branch validation.
- Never trust Company, Customer, programme, balance, conversion factor, amount, account, cost centre, or currency supplied by the browser.
- Do not expose programme expense-account or cost-centre details in the seller summary.
- Preserve all existing User Permission, Company, Branch, Stock Location, pricing, Shipping Rule and Customer filters.
- The native Loyalty Program navigation target is independently filtered by normal DocType read permission.

## Transaction and accounting safety

- Draft creation only.
- No guided submit.
- No submitted Sales Invoice mutation.
- No Sales Invoice cancellation.
- No Loyalty Point Entry write.
- No direct GL Entry or Stock Ledger Entry write.
- No Payment Entry, Journal Entry, refund, write-off, credit note, or stock transaction created by loyalty selection.
- No `ignore_permissions`.
- No manual database commit.
- No shadow points table, custom balance field, custom conversion factor, or duplicated expiry calculation.
- Shipping Rule must be applied before ERPNext validates the requested loyalty value against the final draft total.

## Bounded behaviour

- One Customer and its assigned programme are evaluated per request.
- No unbounded Loyalty Point Entry list is returned.
- ERPNext's aggregate loyalty helper remains the balance authority.
- A changed Customer or posting date clears the requested points and refreshes the summary.
- Stale browser balances cannot authorise redemption; draft creation re-evaluates the current balance.

## Out of scope

- A standalone RetailEdge rewards wallet;
- manual loyalty-ledger corrections;
- programme creation wizard;
- automatic Customer enrolment;
- multiple-programme selection in the guided form;
- loyalty redemption on mapped conversion modes;
- loyalty redemption after a Sales Invoice is submitted;
- reward campaigns outside ERPNext Loyalty Program;
- POSNext/POS Invoice loyalty changes;
- customer-portal redemption;
- automatic invoice submission or payment.

## Migration and compatibility

No RetailEdge DocType, Custom Field, patch, or data migration is required.

The slice relies only on ERPNext v16's existing Customer, Loyalty Program, Loyalty Point Entry and Sales Invoice fields and services. Sites without the relevant ERPNext fields fail closed and retain the native Sales Invoice fallback.

## Required tests

### Backend contract

- programme is derived from Customer, not from browser input;
- Company mismatch fails closed;
- Customer and Company permissions are checked;
- status uses ERPNext's aggregate programme-details-with-points helper;
- expired points remain excluded by ERPNext using the selected posting date;
- response omits expense account and cost centre;
- zero/unassigned cases are non-mutating;
- requested points must be a positive whole number and no greater than current availability;
- current balance is reloaded during draft creation;
- Shipping Rule is applied before loyalty validation;
- ERPNext validation populates native loyalty fields;
- no submitted document or Loyalty Point Entry is written.

### UI/static contract

- Loyalty Program appears once under Pricing & Promotions in approved order;
- the native target remains permission-aware;
- the guided New Invoice mode shows programme, tier, available points and redemption value;
- Customer/posting-date changes clear and refresh loyalty;
- conversion and return modes do not offer guided redemption;
- no Submit action or direct Loyalty Point Entry call is present.

### Regression

Run the complete RetailEdge test suite plus:

- Theme compatibility;
- Linters, Semgrep and dependency audit;
- clean Frappe v16 install/build/migrate/test CI;
- governed EdgeSuite UI candidate compatibility.

## Manual QA deferred to consolidated QA

- Customer with assigned programme and points;
- Customer without programme;
- expired points;
- insufficient points;
- points whose value exceeds the final invoice total;
- Company mismatch;
- Shipping Rule plus loyalty;
- light/dark/mobile behaviour;
- permission-restricted seller;
- native Loyalty Program and Sales Invoice fallbacks;
- submit/cancel/return lifecycle verified through ERPNext after the implementation line is reconciled for browser QA.
