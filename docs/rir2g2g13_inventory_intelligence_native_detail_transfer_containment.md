# RIR2G2G13 — Inventory Intelligence Native Detail and Transfer Containment

## Goal

Keep inventory intelligence and guided stock transfer work in EdgeSuite while containing native Item, Warehouse, Report, DocType and full Stock Entry routes for EdgeSuite-only users.

## Scope

- Inventory Intelligence
- Inventory Ageing
- Transfer Opportunities
- Inventory + Profitability
- Guided Stock Transfer post-save behavior
- Native full Stock Entry fallback

## Required contract

- Both inventory surfaces read `navigation.access.can_use_native_desk` from the authoritative Business Hub context.
- Shell DocType/Report navigation fails closed for EdgeSuite-only users.
- Item and Warehouse values remain visible, but native detail cells are clickable only when Native Desk is available and their handlers independently fail closed.
- Guided Stock Transfer remains available to authorised EdgeSuite users.
- The dialog's full-form fallback is hidden when Native Desk is unavailable.
- Transfer opportunities that require the full Stock Entry form are disabled and explicitly labelled as advanced for EdgeSuite-only users.
- After a guided transfer draft is saved, its Stock Entry identity remains visible in the success alert; automatic native-form navigation occurs only for Native Desk users.
- Inventory calculations, transfer safeguards, filters, exports, scope and cost visibility remain unchanged.

## Safety

- No stock, ageing, replenishment, profitability or transfer calculation changes.
- No Company/Branch/Warehouse scope, option-search, export, role or permission changes.
- No change to guided Stock Transfer creation or ERPNext validation.
- No shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility pass on one exact head.
