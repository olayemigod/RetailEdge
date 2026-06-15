# EdgePay + RetailEdge Limited Sandbox Rollout Log

This document serves as the tracking and monitoring log for the human-led limited sandbox rollout. All test sessions executed by operators must be registered here.

---

## 1. Rollout Session Summary

| Session ID | Rollout Date | Environment / Site | Selected Operators | Operator Roles | Scenario Tested | Status (Pass/Fail) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SR-001** | `2026-06-15` | `posnext.local` (WSL Sandbox) | `Operator Alpha` | Cashier, Reviewer | Standard Cashier checkout & reviewer-assisted reconciliation. | Pass |

---

## 2. Session Detail Log (Session SR-001)

### Rollout Metadata
* **Rollout Date**: `2026-06-15`
* **Environment/Site**: `posnext.local`
* **Selected Operators**: `Operator Alpha`, `Operator Beta`
* **Operator Roles**: Cashier (Alpha), Accounts Reviewer (Beta)

### Scenario Tested
Scenario testing standard checkout flow from POS/Sales Invoice creation to manual payment verification, handoff log consumption, reviewer-assisted Payment Entry submission, and manual Bank Match Review confirmation.

### Transaction References
* **Payment Request Reference**: `EP-PRQ-2026-[REDACTED]`
* **Provider Reference**: `MON-REQ-ACC-SINV-2026-[REDACTED]-TX`
* **Source Document**: `ACC-SINV-2026-00033` (Sales Invoice)
* **Evidence Record**: `RE-EPE-2026-00008` (RetailEdge EdgePay Payment Evidence)
* **Payment Entry**: `ACC-PAY-2026-00168` (Submitted Payment Entry)
* **Bank Transaction**: `ACC-BTN-2026-00009` (Submitted Bank Transaction)
* **Match Review**: `RE-BTM-2026-0096` (RetailEdge Bank Transaction Match)

### Results
* **Expected Result**: Handoff Log processed; Payment Evidence reviewed; Draft Payment Entry created and manually submitted; Bank Match Review successfully associated with a candidate transaction and confirmed.
* **Actual Result**: All stages processed cleanly in sequence; preflight checks passed; standard ledger entries posted on manual submission; match review confirmed and reconciliation status updated.
* **Pass/Fail**: **Pass**

### Issues & Resolutions
* **Issue Found**: None.
* **Severity**: N/A
* **Owner**: `Beta` (Accounts Reviewer)
* **Resolution Status**: Resolved (Standard rollout baseline verified).

### Operator Feedback
1. **Cashier (Alpha)**: Checkout URL loaded correctly in sandbox mode. Idempotency worked when navigating back and forth.
2. **Reviewer (Beta)**: The manual submission preflight guards prevented duplicate matching. The dashboard reports were updated cleanly once matching was confirmed.

### Final Session Recommendation
**GO** - Recommended to continue rollout with additional cashiers and operators.

---

## 3. Empty Rollout Log Template

Use the template below to register new rollout sessions:

```markdown
### Rollout Session [ID]
* **Rollout Date**: YYYY-MM-DD
* **Environment/Site**: [e.g. posnext.local / staging]
* **Selected Operators**: [Operator names]
* **Operator Roles**: [e.g. Cashier, Reviewer, Approver]
* **Scenario Tested**: [Describe the scenario]

#### Transaction References
* **Payment Request Reference**: [Redacted]
* **Provider Reference**: [Redacted]
* **Source Document**: [Link or Name]
* **Evidence Record**: [Link or Name]
* **Payment Entry**: [Link or Name]
* **Bank Transaction**: [Link or Name]
* **Match Review**: [Link or Name]

#### Results
* **Expected Result**: [What was expected]
* **Actual Result**: [What actually happened]
* **Pass/Fail**: [Pass / Fail]

#### Issues & Resolutions
* **Issue Found**: [Details of any bugs/issues]
* **Severity**: [Low / Medium / High / Critical]
* **Owner**: [Name]
* **Resolution Status**: [Open / In Progress / Resolved]

#### Operator Feedback
1. [Usability feedback]
2. [Safety/Integrity feedback]

#### Final Session Recommendation
[GO / NO-GO / DEFERRED - with brief reasoning]
```
