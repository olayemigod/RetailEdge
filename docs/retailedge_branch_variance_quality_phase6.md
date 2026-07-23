# RetailEdge Branch Performance Variance Quality — Phase 6

## Business problem

The Branch Performance Summary previously added signed branch audit variances into one headline card.

That allowed a cash shortage in one branch and a cash overage in another branch to cancel each other. For example:

- Lagos shortage: -1,500
- Abuja overage: +1,000
- signed total: -500
- actual exception exposure: 2,500

The signed total understated the amount requiring investigation.

## Correction

The management KPI is now labelled **Absolute Audit Variance** and sums the absolute value of every branch variance.

The branch-level report column remains **Audit Variance** and continues to show the signed value for each branch.

This separation provides:

- signed row truth for determining shortage versus overage;
- absolute management exposure for understanding the total amount requiring review.

## Scope

Changed:

- Branch Performance native summary card calculation;
- EdgeSuite visible KPI label;
- regression tests;
- documentation.

Not changed:

- branch performance source rows;
- daily audit calculations;
- POS closing calculations;
- cashier expense calculations;
- Sales Invoices or payments;
- branch attribution;
- report filters or columns;
- any accounting or stock document.

## Safety

This phase is read-only and calculation-only.

It adds no write endpoint, migration, patch, DocType field or document mutation.

## Tests

Regression coverage verifies:

1. A shortage and overage do not cancel in the headline KPI.
2. The EdgeSuite metadata selects `Absolute Audit Variance`.
3. The row-level column remains the signed `Audit Variance` currency field.

## Manual QA gate

After clean CI, verify the report with:

- only shortages;
- only overages;
- mixed shortages and overages;
- zero variances;
- multiple permitted branches;
- exported and printed reports.

The sum of the headline KPI should equal the sum of the absolute branch variance values.

## CI dependency

The RetailEdge repository still requires `EDGESUITE_UI_TOKEN` with read-only Contents access to the private `olayemigod/processedge-edge-suite-ui` repository for full build, migration and Frappe test execution.
