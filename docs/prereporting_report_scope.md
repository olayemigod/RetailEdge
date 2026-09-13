# Pre-reporting report read/export scope contract

## Goal

Close direct-report and direct-export Company/Branch scope gaps before new reporting work resumes.

This slice does not add reports or change report calculations. It makes the existing RetailEdge operating-context authority reusable by reporting capability checks, the main screen/export wrappers, and Company-wide stock/accounting control.

## Problem corrected

Older reporting code used two weaker assumptions:

1. some report wrappers looked only at user rows on RetailEdge Branch Profile, so a user governed by the newer RetailEdge Branch Assignment model could bypass that wrapper by omitting Branch; and
2. report capability and Stock & Accounting Integrity logic tried to count `Branch.company`. ERPNext v16 does not provide a native Company field on Branch, so that check returned zero and could incorrectly treat Company-wide access as safe.

A direct export request must never gain broader scope simply because it bypasses the report page or omits Branch.

## Authoritative scope

`retailedge.reporting_scope` now provides the shared server-side reporting scope contract.

### Branch Assignment first

Once a user has RetailEdge Branch Assignment history, active Branch Assignment plus Operating Context option resolution is authoritative. Legacy User Permission, user default and Branch Profile user rows cannot broaden it.

If assignment history exists but there is no active permitted Branch for the selected Company, reporting fails closed.

### Legacy fallback

For users not yet migrated to Branch Assignment, existing User Permission/default and Branch Profile user restrictions remain supported. If none of those restrictions exists, existing legacy Company-wide behavior is preserved; the user is not made Branch-restricted merely because they do not hold a global Branch role.

### Explicit Branch validation

A client-selected Branch is revalidated through `validate_operating_branch`, including Company→Branch setup and current user access. Client filters are never treated as authority.

For a restricted user, a report scope without Branch is rejected for the hardened screen/export wrappers. The user must choose one of the server-authorized Branches. Cross-branch reporting remains available only where the existing access model grants it.

## Hardened paths in this slice

The following screen and export pairs now use the same `constrain_report_filters` boundary:

- Sales by Item
- Sales Invoice Register
- Purchase Register
- Supplier Payables
- Stock Position

The central `get_report_export_data` route also constrains Company/Branch before it performs export capability authorization and before dispatching to the report-owned export handler. This prevents a forged or omitted Branch from turning the generic direct-export endpoint into a wider data path.

Report capability checks now call the same reporting-scope authority rather than using `Branch.company` counting.

## Company-wide Stock & Accounting Integrity

Stock & Accounting Integrity is intentionally a Company-wide accounting control. It cannot be made branch-safe by adding a cosmetic Branch filter to ERPNext's native Stock and Account Value Comparison.

The Company-wide guard therefore follows these rules:

- global Branch-access users retain Company-wide access subject to the existing report/document permissions;
- a user with no configured Branch restriction keeps existing Company-wide behavior;
- a Branch-restricted user is allowed only when RetailEdge can prove that the Company has exactly one Branch across Branch Setup history and that Branch is within the user's current allowed scope;
- if the Company→Branch universe is unknown, or more than one Branch exists in Branch Setup history, the Company-wide review fails closed.

Branch Setup history includes disabled records because historical stock/GL activity from a closed Branch can still be present in a Company-wide accounting comparison.

## Safety and compatibility

This slice does not:

- mutate Sales Invoice, Purchase Invoice, Payment Entry, Stock Ledger Entry, GL Entry, or any other accounting document;
- submit, cancel or amend documents;
- change report formulas, row calculations, pagination limits or native ERPNext accounting truth;
- change `desk_access` or EdgeSuite access mode;
- normalize spaced/unspaced RetailEdge role aliases;
- add a schema migration;
- claim browser/persona QA completion;
- resume C31 or other new reporting development.

## Regression coverage

`test_prereporting_report_scope.py` covers:

- Branch Assignment taking precedence for reporting scope;
- preservation of unrestricted legacy behavior where no Branch restriction exists;
- rejection of omitted Branch for restricted report scope;
- server revalidation of explicit Branch through Operating Context authority;
- fail-closed Company-wide accounting access when the Company Branch universe cannot be proven;
- the safe single-Branch Company-wide exception;
- direct-export filter constraint occurring before capability authorization and dataset dispatch;
- shared screen/export constraint usage for the primary operational reports;
- removal of `Branch.company` assumptions from the Stock & Accounting Integrity guard.

## Remaining scope work

This is the first direct read/export hardening slice. Individual report endpoints that do not use the primary operating-report wrappers still require audit so their direct page API and direct export API cannot diverge. That follow-up must reuse this scope contract rather than creating another Branch authority.

Reporting remains NO-GO until that audit, role normalization, performance review, exact-head validation and persona QA are complete.
