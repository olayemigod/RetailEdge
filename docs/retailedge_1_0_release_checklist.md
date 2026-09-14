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
- Final release-hardening head: `0f9b527d01691a0b477ca9f28f940f04bd1da4ea`
- Governed `version-16` merge commit: `06b9170edd3150394cf827de3827d171605f0463`
- Final hardening gates: Theme #1122, Linters #2963, CI #2984, EdgeSuite Compatibility #1219, Upgrade #129, Browser #235 (24/24 PASS)

## Frozen release order

1. Second full MVP audit — **COMPLETE**
2. Close second-audit gaps — **COMPLETE**
3. Freeze second audit — **COMPLETE**
4. Formal PR #56 RC3 persona/browser acceptance — **COMPLETE / FROZEN**
5. Blocker-only RC3 corrections — **NOT REQUIRED after formal run #234**
6. 1.0.0 release hardening — **COMPLETE**
7. Final exact-head gates — **COMPLETE on `0f9b527d01691a0b477ca9f28f940f04bd1da4ea`**
8. Governed PR #56 merge to `version-16` — **COMPLETE**
9. Recheck promoted release commit/status — **COMPLETE**
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
- [x] Theme Compatibility #1122 green on final hardening exact head
- [x] Linters/Semgrep/dependency audit #2963 green on final hardening exact head
- [x] Clean Frappe v16 CI #2984 green on final hardening exact head
- [x] EdgeSuite UI Candidate Compatibility #1219 green on final hardening exact head
- [x] Upgrade Validation #129 green on final hardening exact head
- [x] Browser Persona #235 green on final hardening exact head — 24/24 PASS
- [x] Final hardening SHA `0f9b527d01691a0b477ca9f28f940f04bd1da4ea` and final six gate run numbers recorded
- [x] PR #56 marked ready only after final six gates were green
- [x] PR #56 merged directly to governed `version-16` base as `06b9170edd3150394cf827de3827d171605f0463`
- [x] Promoted merge commit rechecked on `version-16`; its tree is identical to the fully tested hardening head
- [ ] Create tag `v1.0.0` on the promoted release commit
- [ ] Publish/finalise release notes against the tag

## Promotion rule

Do not create `v1.0.0` directly on the QA working branch.

PR #56 already targets the governed `version-16` release branch. The final tag must point to the merged/promoted `version-16` release commit, not the unmerged QA head.

No new feature scope is permitted during this checklist. Only release metadata/documentation, test/harness corrections, and P0/P1 release blockers may change the candidate.
