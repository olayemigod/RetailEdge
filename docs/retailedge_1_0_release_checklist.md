# RetailEdge 1.0.0 — Release Hardening Checklist

## Authority

- Product: RetailEdge
- Release: 1.0.0
- Authoritative PR: **#56**
- Authoritative branch: `qa/retailedge-visual-identity`
- PR base / governed release branch: `version-16`
- Validated implementation head: `aea2cf4980cfd2dc2b61133ee567f166392a7285`
- Second MVP audit freeze commit: `1bd01c39d7a574df85773aae86fec7a144a98698`
- Formal RC3 accepted head: `099e4a30b2c8a25c2ca0858caa6bcbfe99a8b98c`
- Formal RC3 Browser Persona run: **#234 — 24/24 PASS**
- Retained browser evidence artifact: `10357567550`

## Frozen release order

1. Second full MVP audit — **COMPLETE**
2. Close second-audit gaps — **COMPLETE**
3. Freeze second audit — **COMPLETE**
4. Formal PR #56 RC3 persona/browser acceptance — **COMPLETE / FROZEN**
5. Blocker-only RC3 corrections — **NOT REQUIRED after formal run #234**
6. 1.0.0 release hardening — **IN PROGRESS**
7. Final exact-head gates — **PENDING on release-hardening head**
8. Governed PR #56 merge to `version-16` — **PENDING**
9. Recheck promoted release commit/status — **PENDING**
10. Tag `v1.0.0` — **PENDING**

## 1.0.0 hardening items

- [x] Package version is 1.0.0
- [x] README contains current 1.0 release guidance
- [x] Installation/upgrade notes exist
- [x] 1.0 release notes exist
- [x] Known advanced-native boundaries are documented
- [x] PR #56 second-audit freeze/evidence is recorded
- [x] Formal PR #56 RC3 exact head is recorded
- [x] Formal Browser Persona acceptance is 24/24 PASS
- [x] Retained browser evidence artifact is recorded
- [ ] Confirm Theme Compatibility green on final hardening exact head
- [ ] Confirm Linters/Semgrep/dependency audit green on final hardening exact head
- [ ] Confirm clean Frappe v16 CI green on final hardening exact head
- [ ] Confirm EdgeSuite UI Candidate Compatibility green on final hardening exact head
- [ ] Confirm Upgrade Validation green on final hardening exact head
- [ ] Confirm Browser Persona acceptance green on final hardening exact head
- [ ] Record final hardening SHA and final six gate run numbers
- [ ] Mark PR #56 ready only after final six gates are green
- [ ] Merge PR #56 directly through its governed `version-16` base
- [ ] Recheck release commit/status on `version-16`
- [ ] Create tag `v1.0.0` on the promoted release commit
- [ ] Publish/finalise release notes against the tag

## Promotion rule

Do not create `v1.0.0` directly on the QA working branch.

PR #56 already targets the governed `version-16` release branch. The final tag must point to the merged/promoted `version-16` release commit, not the unmerged QA head.

No new feature scope is permitted during this checklist. Only release metadata/documentation, test/harness corrections, and P0/P1 release blockers may change the candidate.
