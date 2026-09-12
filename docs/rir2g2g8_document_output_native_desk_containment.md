# RIR2G2G8 — Document Output Native Desk Containment

## Goal

Keep Document Output & Sharing fully usable for ordinary EdgeSuite users while preventing the page from opening native ERPNext DocType, Report or full-document routes when Native Desk is unavailable.

## Ownership finding

The EdgeSuite page already owns the ordinary output workflow:
- permission-aware Company/Branch document discovery;
- authenticated Print Preview;
- private PDF download;
- Frappe email with PDF attachment;
- user-initiated WhatsApp handoff.

These output actions do not require Native Desk and remain visible. ERPNext remains the document, Print Format, Letterhead, permission, email and PDF source of truth.

## Current gap

The page previously:
- always rendered **Open Full Document**;
- opened `details.native_route` without checking the EdgeSuite access mode;
- allowed received DocType/Report shell items to open in a new native Desk tab.

The final Business Hub composition already filters ordinary native routes, but the page still requires defense in depth against stale or tampered navigation data and direct/programmatic method invocation.

## Required contract

- Read `navigation.access.can_use_native_desk` from the existing authoritative Business Hub context.
- Hide the full-document action for EdgeSuite-only users and label it as an advanced action when available.
- Fail closed inside `openNativeDocument()` when Native Desk is unavailable.
- Fail closed before DocType/Report shell navigation when Native Desk is unavailable.
- Preserve Page navigation and all output/share actions.
- Preserve existing native behavior for authorised Native Desk users.

## Safety rules

- No source-document mutation.
- No print/PDF/email/WhatsApp backend change.
- No role, permission, Company, Branch or document-search scope change.
- No public PDF link or privacy change.
- No shared EdgeSuite UI runtime change.
- No accounting, stock, payment, workflow or schema change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Tests required

- Native capability is read from Business Hub context.
- Full-document control is capability-gated.
- Full-document handler fails closed.
- DocType/Report shell navigation fails closed.
- Print Preview, PDF, Email and WhatsApp actions remain present.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
