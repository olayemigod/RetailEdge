# RetailEdge — CoreEdge Remote Usage Client Foundation

## Goal

Add a safe RetailEdge client for the CoreEdge V2.6D remote entitlement-usage service without enabling quota
enforcement on Sales Invoice, POS, Purchase, Stock or accounting workflows yet.

This is a transport/configuration foundation only.

## Why this slice is separate

CoreEdge PR #31 introduces remote quota reservation with:

- status;
- reserve;
- finalize;
- release;
- authoritative snapshot.

RetailEdge should not wire those calls into live transaction submission until the central CoreEdge quota PR
chain has passed migration and focused/full-suite validation.

This branch therefore makes the remote contract callable and testable while preserving all current RetailEdge
transaction behaviour.

## Protected site configuration

Credentials must be stored in protected site configuration or a secret manager, not in `RetailEdge Settings`,
Custom Fields, client scripts, browser bundles, logs, or source control.

Canonical shared Service Client keys:

- `coreedge_remote_usage_enabled` — quota-client switch, default 0;
- `coreedge_service_url` — CoreEdge service root URL;
- `coreedge_service_site_identifier` — exact site identifier registered on the CoreEdge Service Client;
- `coreedge_service_api_key` — dedicated Service Client integration-user API key;
- `coreedge_service_api_secret` — dedicated Service Client integration-user API secret;
- `coreedge_service_allow_insecure_http` — default 0; controlled local QA only;
- `coreedge_service_timeout_seconds` — 3–60 seconds, default 15.

These are the same credential names used by the V2.4E context-inventory client, so a RetailEdge site does
not need a second CoreEdge Service Client credential set.

Backward-compatible aliases are accepted when the canonical key is absent:

- `coreedge_base_url`;
- `coreedge_site_identifier`;
- `coreedge_api_key`;
- `coreedge_api_secret`;
- `coreedge_remote_usage_allow_insecure_http`;
- `coreedge_timeout_seconds`.

Canonical `coreedge_service_*` values take precedence when both families are present.

The API secret is excluded from the configuration object's representation and never returned by readiness diagnostics.

HTTPS is required by default. Plain HTTP is rejected unless
`coreedge_service_allow_insecure_http = 1` is explicitly set for controlled local QA.

Example configuration shape:

```json
{
  "coreedge_remote_usage_enabled": 1,
  "coreedge_service_url": "https://coreedge.example.com",
  "coreedge_service_site_identifier": "retail.example.com",
  "coreedge_service_api_key": "<protected-api-key>",
  "coreedge_service_api_secret": "<protected-api-secret>",
  "coreedge_service_allow_insecure_http": 0,
  "coreedge_service_timeout_seconds": 15
}
```

Do not commit a real key or secret.

## Authentication

The client follows the current CoreEdge Service Gateway contract:

```text
Authorization: token <api_key>:<api_secret>
```

RetailEdge does not send Tenant or Product App as trusted request parameters.

CoreEdge derives them from the authenticated Service Client.

## Client module

`retailedge.integrations.coreedge_remote_usage`

Public foundation:

- `get_remote_usage_config()`;
- `get_remote_usage_readiness()`;
- `get_remote_usage_client()`;
- `CoreEdgeRemoteUsageClient.get_usage_status()`;
- `CoreEdgeRemoteUsageClient.reserve_usage()`;
- `CoreEdgeRemoteUsageClient.finalize_usage()`;
- `CoreEdgeRemoteUsageClient.release_usage()`;
- `CoreEdgeRemoteUsageClient.submit_usage_snapshot()`.

## Failure behaviour

The client does not silently invent quota decisions.

It raises explicit integration exceptions for:

- disabled/unconfigured remote usage;
- authentication failure;
- remote platform unavailability;
- invalid service responses.

The later transaction integration must choose fail-closed behaviour deliberately when Block enforcement is enabled.

This client-only slice does not make that business decision because it is not attached to a transaction hook yet.

## No local CoreEdge dependency

The client uses HTTP directly and does not require the `coreedge` app to be installed on the RetailEdge product site.

This supports:

- standalone RetailEdge;
- white-label RetailEdge;
- separately hosted RetailEdge connecting to central CoreEdge.

Existing local CoreEdge adapters remain unchanged for backward compatibility.

## Service paths

The client calls:

- `coreedge.api.v1.service_entitlement_usage.get_usage_status`;
- `coreedge.api.v1.service_entitlement_usage.reserve_usage`;
- `coreedge.api.v1.service_entitlement_usage.finalize_usage`;
- `coreedge.api.v1.service_entitlement_usage.release_usage`;
- `coreedge.api.v1.service_entitlement_usage.submit_usage_snapshot`.

All requests use HTTP POST.

## Tests

Focused suite:

`retailedge.tests.test_coreedge_remote_usage_client`

Coverage includes:

- disabled-by-default behaviour;
- configuration readiness;
- secret-free diagnostics and repr;
- incomplete credentials blocking before network use;
- exact Frappe token authentication;
- exact registered site identifier;
- no Tenant/Product request parameters;
- reserve idempotency/reference forwarding;
- finalize/release/snapshot contract paths;
- authentication-error preservation;
- network/unexpected error normalization;
- invalid response rejection;
- timeout bounds;
- malformed URL rejection;
- HTTPS required by default;
- explicit insecure-HTTP local-QA override;
- canonical shared Service Client config;
- legacy short-key compatibility and canonical-key precedence.

## Out of scope

This branch does not:

- add Sales Invoice hooks;
- add POS Invoice hooks;
- consume quota on draft save;
- enable Block mode;
- create CoreEdge capability grants;
- provision credentials;
- store credentials in RetailEdge Settings;
- change ERPNext accounting;
- mutate submitted documents;
- reserve or debit CoreEdge wallet balances;
- change existing local CoreEdge integration behaviour.

## Next RetailEdge slice

After CoreEdge PR #31 is validated, implement **RetailEdge Sales Transaction Quota Integration** as a separate
narrow branch.

Before coding that hook, lock down:

1. exact Entitlement Key, for example `SALES_TRANSACTIONS`;
2. exactly which committed documents count;
3. whether both POS Invoice and Sales Invoice count, avoiding double counting;
4. the stable idempotency key;
5. the before-submit reserve point;
6. the post-success finalize point;
7. the rollback/release path;
8. cancellation/return policy;
9. offline POS behaviour;
10. operator recovery for a committed ERPNext transaction whose quota finalize acknowledgement was lost.

Do not enable commercial Block enforcement until those rules and the central reservation protocol have passed QA.
