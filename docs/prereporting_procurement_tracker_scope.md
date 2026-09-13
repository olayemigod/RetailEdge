# Pre-reporting Procurement Tracker handoff Company-scope contract

## Business goal

The native ERPNext Procurement Tracker is a Company-wide report with no safe Branch filter. RetailEdge may expose its handoff only when the current reader has unrestricted reporting scope for the selected Company, not merely when a global-role helper returns true.

## B4B23 scope

This slice hardens only the Procurement Tracker capability handoff. It replaces the global-role availability decision and legacy explicit-Branch validator with the authoritative reporting-scope contract. It does not execute, reproduce, filter, persist or modify the native Procurement Tracker dataset.

## Handoff contract

- Company resolution and Company read permission remain mandatory.
- A selected Branch is revalidated for the current reader and selected Company through `validate_report_scope`.
- Any selected Branch keeps the Company-wide native report handoff unavailable.
- Blank-Branch availability requires `has_unrestricted_report_scope` for the resolved Company.
- Global readers and compatible legacy readers with no configured Branch restriction remain eligible.
- Branch Assignment-restricted, restricted-zero, legacy-restricted, Company-denied and scope-error readers remain ineligible.
- Native Report read permission and Purchase Order read permission remain mandatory.
- Missing Company, missing/unreadable Report and missing Purchase Order permission continue to fail closed with no native report execution.

## Preserved composition

- ERPNext `Procurement Tracker` remains the only report and source of truth.
- RetailEdge returns capability metadata only; it does not import or execute the native report engine.
- Professional Purchasing continues to open the native Query Report with Company context and without a Branch route option.
- RFQ, Supplier Quotation, Purchase Order, Purchase Receipt and all draft-first purchasing workflows remain unchanged.
- No query, posting, document mutation, Business Hub change or QA-composition change is introduced.

## Deferred manual QA

Browser/persona validation remains part of the reconciled manual QA pass. Verify the Professional Purchasing action as unrestricted owner, unrestricted legacy manager, restricted single/multi/zero Branch users, Company-denied user, report-denied user and Purchase Order-denied user. Confirm the action remains hidden for any selected Branch and opens only the native Company-scoped report when eligible.
