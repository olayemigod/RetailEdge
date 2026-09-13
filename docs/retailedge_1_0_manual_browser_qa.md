# RetailEdge 1.0.0 — Final Manual Browser QA

## Authority

- Release branch: `version-16`
- Release candidate SHA: `36fc9302aec80c13d8dd6ec8195486b490b33553`
- Package version: `1.0.0`
- Automated RC3: 21/21 PASS
- Promotion gates: 6/6 PASS
- Manual QA state: **IN PROGRESS**
- Tag state: **BLOCKED until manual QA passes**

## Rules

- Test the actual `version-16` release candidate, not an older QA branch.
- Record PASS / FAIL / BLOCKED with screenshot or clear observation where useful.
- Only P0/P1 release blockers may change code.
- Any code correction invalidates the candidate SHA and requires affected/final gate reruns.
- Do not create `v1.0.0` until this document is frozen PASS.

## Gate 0 — Release preflight

| Check | Status | Evidence |
| --- | --- | --- |
| Site code is on release candidate / version-16 | PENDING | |
| `bench --site <site> migrate` completed | PENDING | |
| Assets rebuilt / cache cleared | PENDING | |
| No obvious server/asset error on login | PENDING | |

## Gate 1 — Owner / Manager: Business Hub

| Check | Status | Evidence |
| --- | --- | --- |
| Business Hub opens as normal RetailEdge home | PENDING | |
| One EdgeSuite product shell; no competing native sidebar | PENDING | |
| Company / Branch context is understandable | PENDING | |
| Today cards render cleanly | PENDING | |
| Stock section renders cleanly | PENDING | |
| Banking section renders cleanly | PENDING | |
| Branch section renders cleanly | PENDING | |
| Cash Shift / Attention signals render cleanly | PENDING | |
| Quick actions are visible and sensible | PENDING | |
| + Create opens and is searchable | PENDING | |
| Product menu opens with Ctrl/Cmd+K | PENDING | |
| No visible runtime error/modal/404 | PENDING | |

## Remaining gates

2. Owner/Manager Action Centre and key navigation
3. Cashier persona
4. Accounts persona
5. Stock persona
6. Purchasing persona
7. Sales persona
8. Branch Manager / one-Branch / multi-Branch / zero-Branch isolation
9. Banking readiness and Bank Matching
10. Expenses: Business Expense vs Cashier Expense routing
11. Guided stock completion and branch/warehouse filtering
12. Light/Dark mode, narrow/mobile, keyboard/save safety
13. Final release smoke and tag decision

## Final decision

**NOT YET PASSED**
