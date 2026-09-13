# RIR2G2G9 — Action Centre Native Workflow Containment

## Goal

Keep exception truth and follow-up management visible in Action Centre while preventing EdgeSuite-only users from opening retained native DocType or Query Report workflows.

## Ownership finding

Action Centre is a read/control surface. It composes authoritative exceptions and owns only follow-up metadata such as acknowledgement, assignment, scheduling and snooze. Business resolution remains in each owning EdgeSuite Page or deliberate advanced ERPNext workflow.

## Current gap

Action rows carry `target_type`, but `openWorkflow()` previously used only the route. Native DocType/Report exception routes could therefore open even when the user had no Native Desk capability. Shell navigation also lacked page-level defense in depth.

## Required contract

- Read `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- EdgeSuite Page and approved non-native workflow routes remain actionable.
- Native DocType/Report workflows remain visible as exception truth but their action is disabled and labelled **Advanced workflow** for EdgeSuite-only users.
- `openWorkflow()` fails closed for retained native target types when Native Desk is unavailable.
- Shell DocType/Report navigation fails closed under the same condition.
- Authorised Native Desk users retain existing same-tab/new-tab behavior.

## Safety rules

- Do not hide exception values, sources, severity, prioritisation or follow-up state.
- Do not mutate underlying accounting, stock, payment, banking or workflow documents.
- Do not change Action Follow Up persistence semantics.
- Do not change Company/Branch scope, roles, permissions or source-provider composition.
- Do not change shared EdgeSuite UI runtime.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
