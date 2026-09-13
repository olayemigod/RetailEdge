# RetailEdge 1.0.0 — Release Hardening Checklist

## Authority

- Product: RetailEdge
- Release: 1.0.0
- Authoritative PR: #55
- QA branch: qa/retailedge-reconciled-20260902
- PR base: qa/retailedge-consolidated-20260829
- Repository release/default branch: version-16
- RC3 implementation accepted: 202741c34abd76d53521e3d60f0a69d1557a9a87
- RC3 documentation freeze head: 1347ee447900a9ec94fd4c0c9eea9d19144f6865

## Frozen release order

1. Second full MVP audit — COMPLETE
2. Close second-audit gaps — COMPLETE
3. Freeze second audit — COMPLETE
4. RC3 persona/browser acceptance — COMPLETE
5. Blocker-only RC3 corrections — COMPLETE
6. RC3 freeze and exact-head revalidation — COMPLETE
7. 1.0.0 release hardening — IN PROGRESS
8. Final exact-head gates — PENDING
9. Governed branch promotion/merge — PENDING
10. Tag v1.0.0 — PENDING

## 1.0.0 hardening items

- [x] Promote package version from 0.0.1 to 1.0.0
- [x] Add current README 1.0 release guidance
- [x] Add installation/upgrade notes
- [x] Add 1.0 release notes
- [x] Document known advanced-native boundaries
- [x] Preserve RC3 freeze/evidence record
- [ ] Confirm Theme Compatibility green on hardening exact head
- [ ] Confirm Linters/Semgrep/dependency audit green on hardening exact head
- [ ] Confirm clean Frappe v16 CI green on hardening exact head
- [ ] Confirm EdgeSuite UI Candidate Compatibility green on hardening exact head
- [ ] Confirm Upgrade Validation green on hardening exact head
- [ ] Confirm Browser Persona acceptance green on hardening exact head
- [ ] Record final hardening SHA
- [ ] Make PR #55 ready only after the final six gates are green
- [ ] Merge PR #55 through its governed QA base
- [ ] Promote the reconciled release candidate to version-16
- [ ] Recheck release commit/status on version-16
- [ ] Create tag v1.0.0 on the promoted release commit
- [ ] Publish/finalise release notes against the tag

## Promotion rule

Do not create v1.0.0 directly on the QA working branch.

PR #55 currently targets qa/retailedge-consolidated-20260829, while the repository release/default branch is version-16. The accepted candidate must move through the governed merge/promotion path so the final tag represents the release branch history, not an unmerged QA branch.

No new feature scope is permitted during this checklist. Only release metadata/documentation, test/harness corrections, and P0/P1 release blockers may change the candidate.
