# R10 Stock Cover Review Contract

## Purpose

RetailEdge R10 needs a practical way to surface inventory that may deserve excess-stock review without inventing a universal overstock rule or a demand forecast.

ERPNext remains authoritative for current stock, stock valuation and reorder configuration. RetailEdge adds only an advisory interpretation of observed demand evidence.

## Definition

`High Cover Review` applies only when:

1. the item has positive observed average daily demand in the selected evidence window;
2. current available quantity is taken from the permission-scoped ERPNext Bin position;
3. estimated stock cover is calculated as `available quantity / observed average daily demand`; and
4. estimated stock cover is greater than the selected evidence-window length.

Example: with a 90-day evidence window, an item with 120 estimated days of cover is flagged for High Cover Review. An item with exactly 90 days of cover is not flagged.

## What the Signal Means

The signal means only that current available stock would last longer than the historical evidence window if the observed average daily demand rate continued unchanged.

It is a management review cue for questions such as:

- Is purchasing still appropriate?
- Should stock be transferred to another permitted location?
- Is the item slow-moving or becoming obsolete?
- Is a promotion or pricing review justified?
- Should management inspect ageing before ordering more?

## What the Signal Does Not Mean

High Cover Review is not:

- an ERPNext stock balance or valuation;
- a maximum-stock policy;
- proof that stock is overstocked;
- a sales or demand forecast;
- an instruction to discount, transfer, purchase or write off stock;
- a replacement for ERPNext Item Reorder configuration;
- persistent inventory truth.

No document is created, submitted or mutated by this classification.

## Relationship to Inventory Ageing

High Cover Review and Inventory Ageing answer different questions.

- **Stock cover** uses current available stock and bounded observed outward demand.
- **Inventory Ageing** uses ERPNext v16 Stock Ageing `FIFOSlots` semantics to reconstruct the age of stock currently on hand.

Inventory Ageing is the authoritative R10 surface for aged quantity and, where RetailEdge cost visibility permits, aged stock value/capital tied up.

An item may have high cover without being old, or old stock without enough recent demand evidence to calculate cover. RetailEdge must not collapse these signals into one unsupported overstock conclusion.

## Permissions and Cost Visibility

The stock-cover review classification does not require valuation or cost fields. Users without RetailEdge cost visibility may still see the operational High Cover Review signal.

Aged stock value and other capital-value measures remain protected by the existing RetailEdge cost-visibility policy and must not be queried or returned to restricted users.

## Performance and Scope

The review uses the same bounded, permission-aware Inventory Health composition already used by R10:

- ERPNext Bin for current stock;
- bounded historical outward Stock Ledger Entry evidence for demand;
- the selected Company → Branch → Warehouse → Item Group → Item scope;
- the user-selected evidence window.

No additional full-ledger scan or persistent derived table is introduced.