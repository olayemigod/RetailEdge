# RetailEdge → CoreEdge V2.4 Context Normalizer

RetailEdge does not replace its operating-context rules for CoreEdge adoption.

The authoritative local identity is:

`RetailEdge Branch Profile.company + RetailEdge Branch Profile.branch`

ERPNext v16 Branch is not treated as Company-bound by itself. The Branch Profile remains the RetailEdge authority for Company, POS, pricing, warehouse, accounting defaults and operational controls.

`retailedge.integrations.context_reconciliation.get_context_reconciliation_rows()` only exports a read-only normalized view for CoreEdge reconciliation.

It does not:

- import CoreEdge;
- create or modify Branch Profiles;
- switch Company or Branch;
- grant branch access;
- change POS, pricing, stock or accounting defaults;
- mutate ERPNext accounting documents.

When historical disabled and current enabled profiles exist for the same Company + Branch, the enabled/current profile is emitted once. Disabled-only identities remain visible as inactive reconciliation rows.

A later integration phase may send these rows to CoreEdge V2.4B, but confirmed CoreEdge mappings must not replace RetailEdge's local authorization or configuration checks.
