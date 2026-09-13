# RIR2F2A — Purchase Invoice EdgeSuite Ownership

## Status

Implementation checkpoint on PR #55. Freeze only after all required CI gates pass on one commit SHA.

## Goal

Make the normal RetailEdge Purchase Invoice path EdgeSuite-first without changing ERPNext purchasing, stock, tax, accounting, submission, cancellation, or permission semantics.

## Ownership contract

- Guided Purchase Invoice creation remains the normal RetailEdge create path.
- Submitted Purchase Invoice browsing is owned by the EdgeSuite `purchase-register` Page.
- The normal Buy navigation must not show a peer native `Purchase Invoice` DocType route when the current user can open Purchase Register and Purchase Register is present in the final Buy composition.
- If Purchase Register is unavailable or absent from the final composition, native Purchase Invoice remains as a compatibility fallback so the user is not stranded.
- Transaction Workspace `View / Manage` for Purchase Invoice routes to `purchase-register`.
- Transaction Workspace disables the Purchase Invoice native-form escape.
- Where a native Purchase Invoice escape is deliberately retained for a Native-Desk-authorised user, it is presented explicitly as `Advanced: Open in ERPNext`.

## Deliberately unchanged in RIR2F2A

- Purchase Order remains a peer/native-capable path pending RIR2F2B integration of the existing guided Professional Purchase Order dialog into Professional Purchasing.
- Purchase Receipt remains native because detailed receipt/return review still intentionally delegates to ERPNext stock truth.
- RFQ, Supplier Quotation, Purchase Order Analysis, Procurement Tracker, Landed Cost Voucher, incoming quality workflow, and submitted-document review are not promoted or rewritten here.
- No role, DocType permission, Branch Assignment, User Permission, accounting, GL, Stock Ledger, pricing, tax, submission, cancellation, amendment, or migration behavior changes.

## Safety

ERPNext remains the system of record. RIR2F2A changes route ownership and presentation only. Guided Purchase Invoice creation continues to create a draft through existing server-side RetailEdge/ERPNext validation and branch-aware context.

## Required tests

- Purchase Register available and present: native Purchase Invoice peer is removed.
- Purchase Register unavailable: native Purchase Invoice peer remains.
- Purchase Register missing from composition: native Purchase Invoice peer remains.
- Transaction Workspace guided create remains EdgeSuite.
- Transaction Workspace read/manage routes to Purchase Register.
- Transaction Workspace has no Purchase Invoice native escape.
- Any retained Purchase Invoice native escape is explicitly advanced and permission-controlled.
- Existing Selling, POS, Stock and purchasing safety tests remain green.

## Next bounded slice

RIR2F2B: integrate the existing `ProfessionalPurchaseOrderDialog.vue` into `ProfessionalPurchasing.vue`, then remove native Purchase Order as a peer everyday Buy route only after the guided create/read contract is proven. Purchase Receipt ownership remains a separate decision after that.
