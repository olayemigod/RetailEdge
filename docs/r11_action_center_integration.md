# RetailEdge R11.7 — Customer & Sales Action Centre Integration

## Goal

Surface a small set of actionable R11 customer/sales signals in the existing RetailEdge Action Centre without creating a new task engine, customer-risk ledger, sales-quality state machine or duplicate receivables provider.

## Action domains

R11.7 adds aggregate actions for:

- Customer retention follow-up.
- Customer growth opportunities.
- High recorded price-reduction invoices.
- Low or negative transactional-margin invoices when cost visibility permits.

R11.7 deliberately does **not** add a second overdue-receivables action. Current overdue exposure remains owned by the existing Action Centre Receivables provider.

Basket & Product Affinity remains insight-only. A co-purchase relationship is not, by itself, an exception or required task.

## Source contract

The provider reuses:

- R11.3 Customer Retention & Opportunity Intelligence.
- R11.6 Discount & Sales Quality.
- Existing Company/Branch/date permission scope resolved by Action Centre.
- Existing RetailEdge cost-visibility rules.

No new customer, sales, discount, receivable or profitability truth is persisted.

## Stable action identities

The new semantic identities are:

- `r11_customer_opportunity / customer_retention_follow_up`
- `r11_customer_opportunity / customer_growth_opportunity`
- `r11_sales_quality / high_price_reduction`
- `r11_sales_quality / low_or_negative_transactional_margin`

These feed the existing Action Follow Up fingerprint contract. Acknowledgement, assignment, snooze and follow-up dates remain metadata on `RetailEdge Action Follow Up`; they do not mutate or resolve the underlying customer/sales condition.

If the source condition no longer exists on a later refresh, the generated action naturally disappears from the current Action Centre. Historical follow-up state does not manufacture an open business exception.

## Business Control Centre compatibility

Action Follow Up writes re-resolve the requested fingerprint through Business Control Centre. Because Business Control Centre composes the canonical Action Centre payload, R11 actions remain visible during that permission-aware re-resolution without any parallel write path.

## Failure isolation

The R11 source uses the existing Action Centre `_safe_source` contract.

- Permission denial hides only the R11 source.
- A bounded-scan/validation failure marks only the R11 source unavailable.
- The rest of Action Centre remains operational.
- Raw validation details are not leaked in the source reason.

## Severity and routing

- Retention follow-up: warning → Customer Retention & Opportunity Intelligence.
- Growth opportunity: info → Customer Retention & Opportunity Intelligence.
- High recorded price reduction: warning → Discount & Sales Quality.
- Low/negative transactional margin: warning → Discount & Sales Quality, only when cost visibility permits.

These EdgeSuite pages open in the same tab. Any native ERPNext drill-through retained inside those pages continues to open in a new tab.

## Tests

Coverage includes:

- non-duplicate action-domain selection;
- cost-restricted suppression of margin actions;
- stable source/kind/semantic identities;
- existing Action Follow Up fingerprint decoration;
- Business Control Centre preservation for follow-up re-resolution;
- R11 source failure isolation.

Manual/browser QA remains deferred until the predecessor stack is promoted and R11 is reconciled onto the promoted R10 head.
