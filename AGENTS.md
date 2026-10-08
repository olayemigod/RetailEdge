# RetailEdge Agent Instructions

## Mandatory canonical skill
Before planning, editing, implementing, reviewing, testing, creating a branch/PR, performing QA, migration, release, or any other RetailEdge operation, load and follow:

https://github.com/olayemigod/processedge-qa/blob/main/skills/processedge-frappe-product-engineering/SKILL.md

Re-read the canonical skill at the start of each new work session and whenever the task changes materially.

## Pre-work gate
Before modifying code, check the canonical skill, repository-specific instructions/docs, authoritative `version-16` base, outstanding PRs/dependencies, native ERPNext behavior, existing EdgeSuite/shared implementation, required permission personas/tests, and the smallest bounded mergeable slice.

## Existing RetailEdge locked-candidate invariant
Do not continue R5.6 or any new feature work until the R5.5 candidate drift regression is fixed with failing regression tests first.

The most important invariant is:

Selected report row candidate == batch job row locked candidate == Bank Match Review candidate == confirmation candidate.

The backend may validate the locked candidate, but it must never replace it with current-best candidate.

## Product boundary
RetailEdge extends ERPNext selling, buying, stock, payments and retail operations without replacing ERPNext accounting/stock truth. EdgeSuite is the normal guided surface; authorized native ERPNext remains Advanced. Product-neutral UI behavior belongs in EdgeSuite UI. These repository-specific rules extend, but do not silently weaken, the canonical skill.
