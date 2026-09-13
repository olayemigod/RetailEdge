# RIR2G2G3 — Branch Performance Native Desk Containment

## Goal

Close page-level Native Desk escape paths from Branch Performance for EdgeSuite-only users while preserving deliberate native Report/DocType access for users whose shared access context allows Native Desk.

## Current gap

RIR2G2A already filters raw DocType/Report navigation at server composition and protects Business Hub routing. Branch Performance still has its own page-level routing paths:

- `handleNavigation()` directly opens Query Reports and DocType lists when such an item reaches the page;
- the `Detailed Report` action is always visible;
- `openDetailReport()` directly opens the native `RetailEdge Branch Performance Summary` Query Report;
- the page does not currently retain `navigation.access.can_use_native_desk`.

This creates a defense-in-depth gap for stale/tampered navigation or direct page actions.

## Required contract

- Default page state must fail closed with Native Desk disabled.
- Read `navigation.access.can_use_native_desk` from the same shared Business Hub context already used for navigation.
- The Detailed Report button is shown only when Native Desk is allowed.
- `handleNavigation()` must return before routing a Report or DocType when Native Desk is disabled.
- `openDetailReport()` must return before routing when Native Desk is disabled.
- EdgeSuite Page navigation remains available.
- Native-Desk-capable users retain current Report/DocType routing subject to the existing server-side permission-aware composition.

## Safety rules

- No ERPNext/Frappe permission, role or desk-access changes.
- No Branch Performance data, calculation, SQL, export or print changes.
- No Branch Assignment, Company or Branch semantics change.
- No accounting, stock, payment, workflow or submitted-document mutation.
- No shared EdgeSuite UI runtime changes.
- No replacement EdgeSuite report is introduced in this slice.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests required

- Page defaults Native Desk capability to false.
- Page derives capability only from `navigation.access.can_use_native_desk`.
- Detailed Report action is hidden without Native Desk capability.
- Generic navigation fails closed for Report/DocType targets without Native Desk.
- Detailed Report routing fails closed without Native Desk.
- Existing Page navigation remains unchanged.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
