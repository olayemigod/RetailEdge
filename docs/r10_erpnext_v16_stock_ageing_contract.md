# R10 ERPNext v16 Stock Ageing Contract

## Purpose

This note records the ERPNext v16 Stock Ageing behaviour that RetailEdge R10 must preserve before implementing inventory ageing and capital lock-up intelligence.

RetailEdge must not replace ERPNext Stock Ageing with a cheaper `last movement date` approximation and present that approximation as stock ageing.

## Verified ERPNext v16 Source

ERPNext v16 implements Stock Ageing in:

- `erpnext/stock/report/stock_ageing/stock_ageing.py`

The report reconstructs FIFO-style slots for stock that remains on hand and uses those slots to calculate age quantities and values.

## Core Semantics

### 1. Age is slot-based, not simply item-last-movement age

ERPNext `FIFOSlots` maintains stock slots containing quantity, posting date and value information for remaining stock.

The report calculates an age for each remaining slot using the selected `to_date` and the slot posting date.

Therefore:

- `days since last demand` is not Stock Ageing;
- `days since last stock movement` is not Stock Ageing;
- `days since last receipt` by itself is not Stock Ageing;
- R10 movement-recency metrics must remain clearly separate from FIFO Stock Ageing.

### 2. Average age is quantity weighted

ERPNext calculates average age by multiplying each remaining slot age by its quantity and dividing by the total remaining quantity.

R10 must not use an unweighted average of receipt or movement dates.

### 3. Age buckets contain both quantity and value

ERPNext assigns each remaining FIFO slot to an age bucket and accumulates:

- quantity; and
- stock value.

This is the correct foundation for R10 capital-lock-up intelligence.

Any value-based R10 ageing surface must remain subject to RetailEdge cost/valuation visibility rules at the backend/query boundary.

### 4. Earliest and latest age are based on remaining FIFO slots

ERPNext reports the age of the earliest and latest remaining slots. These are not generic first/last Stock Ledger Entry dates.

### 5. Batch and serial behaviour is specialised

ERPNext normalises batch valuation slots into the common reporting shape and treats serial-number slots with serial-specific quantity semantics.

R10 must not flatten batch/serial ageing into a generic non-batch calculation unless ERPNext already does so through the Stock Ageing engine.

### 6. Moving Average valuation remains ERPNext-owned

For Moving Average items, ERPNext recomputes slot values using the item valuation rate when preparing ageing data.

RetailEdge must not independently reconstruct those valuation values.

## R10 Implementation Rule

R10D should consume or safely adapt ERPNext v16 Stock Ageing/FIFO-slot semantics rather than implementing a second ageing engine.

The adapter must add RetailEdge concerns around the ERPNext truth:

- Company/Branch/Warehouse scope;
- Item Group/Item scope;
- permission-aware source filtering;
- cost visibility;
- bounded execution/performance protection;
- EdgeSuite presentation;
- action-oriented ageing and capital-lock-up classifications.

It must not change the underlying ageing mathematics.

## Candidate R10 Age Bands

RetailEdge may present business-friendly bands such as:

- 0–30 days;
- 31–60 days;
- 61–90 days;
- 91–180 days;
- 181+ days.

These bands are presentation/configuration choices only. The quantities and values assigned to them must come from ERPNext FIFO-slot ageing semantics.

## Permission and Performance Gate

Before exposing R10D to users, implementation must prove that:

1. only warehouses inside the resolved RetailEdge permission scope can contribute Stock Ledger Entries;
2. only permitted Items can be returned;
3. valuation/value fields are not fetched or returned when RetailEdge cost visibility denies them;
4. the ageing scan is bounded or requires a sufficiently narrow scope;
5. no submitted stock document is mutated;
6. no parallel ageing or valuation persistence is introduced.

Until those conditions are met, R10 should continue using the already-implemented movement-recency fields under their correct labels rather than mislabelling them as ageing.
