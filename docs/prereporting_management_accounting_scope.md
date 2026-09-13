# Pre-reporting management accounting visibility scope contract

## Business goal

Company-level accounting balances, profitability and early-warning trends must be visible only when the current reader has an unrestricted reporting scope for the selected Company. A global-role shortcut cannot represent Company-specific Branch Assignment state or the compatible unrestricted state of a legacy user with no configured Branch restriction.

## B4B21 scope

This slice introduces one fail-closed Company reporting-scope predicate and reuses it for accounting visibility in Financial Position, Liquidity Control, Business Control and Control Early Warning. It does not change the underlying Owner Dashboard, cash movement, receivables, payables, accounting profitability, budget, or warning engines.

## Visibility contract

- Company is mandatory before Company-wide accounting visibility can be granted.
- Company read permission and Branch scope are resolved for the current reader through `validate_report_scope`.
- Global-role users and legacy users with no configured Branch restriction remain unrestricted through the existing reporting-scope contract.
- Branch Assignment-restricted users, restricted-zero users, Company-denied users and scope-resolution failures are not treated as Company-wide readers.
- Any explicit Branch filter continues to withhold Company-level accounting balances and profitability because safe Branch accounting-dimension attribution is not inferred.
- Operational, receivable, payable, cash-movement and transactional-margin data continue to use their existing hardened engines and filter contracts.

## Preserved composition

- Financial Position still composes the Owner Dashboard with the permission-aware ERPNext account-balance helper.
- Liquidity Control still composes cash movement, current receivables, current payables and permitted company-level cash/bank balances without reloading the full Owner Dashboard.
- Business Control still derives its cards and controls from the existing Owner Dashboard payload.
- Control Early Warning still composes budget, liquidity and accounting-profitability services without manufacturing historical receivable or payable balances.
- Dashboard capabilities, exports, Action Centre/Business Control Centre composition, follow-up state transitions, business documents and all mutations are unchanged.
- Business Hub implementation remains outside this slice.

## Regression matrix

- unrestricted global reader: Company accounting visibility allowed;
- unrestricted legacy reader: Company accounting visibility allowed;
- restricted single/multi/zero Branch reader: Company accounting visibility denied;
- missing or unauthorized Company: visibility denied;
- explicit Branch: Company accounting visibility denied even for an unrestricted reader;
- scope-resolution failure: visibility denied without falling back to a global-role assumption.

## Deferred manual QA

Browser/persona validation remains part of the reconciled manual QA pass. Verify the four management surfaces as unrestricted owner, unrestricted legacy manager, restricted Branch manager, restricted-zero reader user, and Company-denied user. Confirm accounting cards and trends are withheld without changing operational cards, navigation or actions.
