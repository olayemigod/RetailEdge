# RetailEdge — CoreEdge Remote Quota Client Foundation

## Goal

Prepare RetailEdge to use CoreEdge V2.6D remote entitlement usage services without changing any live Sales Invoice, POS, purchase, stock or accounting workflow yet.

This slice is transport and adapter infrastructure only.

## Why this is separate

RetailEdge historically integrates with CoreEdge primarily through local Python imports when CoreEdge is installed on the same bench.

ProcessEdge's long-term deployment model also requires standalone and white-label product sites to connect to central CoreEdge services.

Remote quota enforcement must therefore use the authenticated CoreEdge Service Gateway rather than importing CoreEdge code locally.

## Visible RetailEdge settings

`RetailEdge Settings` adds two non-secret switches:

- `Enable Remote CoreEdge Services`
- `Enable CoreEdge Quota Integration`

Quota Integration cannot be enabled unless Remote CoreEdge Services is enabled.

Both switches default to off.

Enabling these switches does **not** attach quota enforcement to any RetailEdge transaction in this slice.

## Protected configuration

Credentials are not stored in RetailEdge Settings or any normal DocType.

Provide the following through protected `site_config.json`, environment-backed deployment configuration, or a secret manager:

- `coreedge_service_url` — central CoreEdge base URL;
- `coreedge_service_site_identifier` — exact site identifier registered on the CoreEdge Service Client;
- `coreedge_service_api_key` — dedicated CoreEdge integration user's API key;
- `coreedge_service_api_secret` — dedicated CoreEdge integration user's API secret;
- `coreedge_service_client_id` — optional expected client ID used to validate the response scope;
- `coreedge_service_timeout_seconds` — optional timeout, bounded to 2–60 seconds.

CoreEdge credentials must be issued through the central Service Client provisioning workflow.

Do not place credentials in:

- RetailEdge Settings;
- client-side JavaScript;
- browser bundles;
- source control;
- logs;
- support messages;
- committed deployment files.

## Authentication

RetailEdge uses normal Frappe token authentication exactly as required by the current CoreEdge Service Gateway:

`Authorization: token <api_key>:<api_secret>`

The API key and secret belong to the dedicated non-Desk CoreEdge Service Client integration user.

HTTP is allowed only for localhost / `.local` development endpoints. Non-local CoreEdge service URLs must use HTTPS.

## Remote transport

`retailedge.integrations.coreedge_remote.RemoteCoreEdgeClient` provides the shared server-side transport.

It:

- accepts only versioned `coreedge.api.v1.*` service methods;
- injects the configured `site_identifier` server-side;
- does not allow the caller to override that site identity;
- sends JSON POST requests;
- unwraps standard Frappe `message` responses;
- validates returned site identity;
- optionally validates returned CoreEdge client ID;
- distinguishes configuration, authentication, availability and response-contract errors;
- redacts API key/secret from the configuration object's Python representation.

## Quota adapter

`retailedge.integrations.quota` exposes:

- `get_usage_status()`;
- `reserve_usage()`;
- `finalize_usage()`;
- `release_usage()`;
- `submit_usage_snapshot()`.

The adapter targets:

- `coreedge.api.v1.service_entitlement_usage.get_usage_status`;
- `coreedge.api.v1.service_entitlement_usage.reserve_usage`;
- `coreedge.api.v1.service_entitlement_usage.finalize_usage`;
- `coreedge.api.v1.service_entitlement_usage.release_usage`;
- `coreedge.api.v1.service_entitlement_usage.submit_usage_snapshot`.

RetailEdge never sends Tenant or Product App as trusted request fields. CoreEdge derives them from the authenticated Service Client.

## Local validation

RetailEdge rejects malformed requests before making a remote call:

- Entitlement Key: required, max 140 characters;
- consume Units: positive whole number;
- snapshot Usage Value: non-negative whole number;
- idempotency key: 1–140 characters using letters, numbers, dots, underscores, colons and hyphens;
- reservation TTL: 60–3600 seconds;
- release reason: 5–500 characters.

CoreEdge remains the final authority for entitlement state, quota policy, Tenant/Product scope, Service Client status and capability grants.

## Current integration status

`get_coreedge_status()` now exposes secret-free flags:

- local CoreEdge installed/enabled state;
- remote services enabled;
- remote services configured;
- remote credentials present;
- remote quota integration enabled.

No API key or secret is returned.

## Explicit safety boundary

This branch does **not**:

- hook Sales Invoice `before_submit`, `on_submit`, `validate` or `after_submit` for quota;
- hook POS Invoice;
- count POS transactions;
- count Purchase Invoices or Receipts;
- count stock movements;
- create or map commercial Entitlement Keys;
- enable Block mode for any customer;
- reserve quota when a form opens or a draft is saved;
- mutate submitted ERPNext documents;
- change ERPNext GL, payment, stock or accounting behavior.

The test suite contains a regression asserting that `hooks.py` and `events/sales_invoice.py` do not import or call the quota adapter in this client-foundation slice.

## Future RetailEdge transaction integration

After CoreEdge PR #31 passes central validation, implement the first real counted RetailEdge event as a separate PR.

For a Sales Invoice transaction quota, the future workflow should be designed around the exact final submission path:

1. validate the draft invoice using normal ERPNext/RetailEdge rules;
2. immediately before final submit, reserve one quota unit using a stable business idempotency identity;
3. if CoreEdge blocks the reservation, do not submit;
4. submit the Sales Invoice through normal ERPNext behavior;
5. after successful commit, finalize the reservation;
6. if submission fails before commit, release the reservation;
7. if the finalize response is lost, retry finalize with the same idempotency key.

Do not count:

- draft saves;
- form opens;
- report views;
- print actions;
- cancelled submissions unless the future commercial policy explicitly defines a compensating quota rule.

Before enabling this flow, define whether POS Invoice and Sales Invoice are one shared commercial transaction allowance or separate Entitlement Keys. Do not double count a POS flow that synchronizes into another sales document.

## Tests

Focused test module:

`retailedge.tests.test_coreedge_remote_quota_client`

Coverage includes:

- Frappe token authentication header;
- server-bound site identifier;
- caller site-identity override prevention;
- returned CoreEdge client/site scope validation;
- versioned method restriction;
- HTTPS requirement outside local development;
- API key/secret redaction from config repr and status;
- exact V1 quota endpoint routing;
- no Tenant/Product request parameters;
- stable idempotency/reference forwarding;
- local invalid-request rejection before transport;
- disabled quota fail-closed behavior;
- settings dependency validation;
- settings schema contains no remote credential fields;
- no Sales Invoice quota hook in this slice.

## Migration

Run normal `bench migrate` so the two new RetailEdge Settings switches are available.

No data patch is required.

No site is enabled automatically.

No existing CoreEdge local integration setting changes behavior.

## Manual QA

On a non-production RetailEdge site:

1. migrate the site;
2. confirm Remote CoreEdge Services and Quota Integration are off by default;
3. provision a sandbox RetailEdge Service Client centrally in CoreEdge;
4. securely configure the six protected keys above without exposing the secret in logs or source control;
5. enable Remote CoreEdge Services;
6. enable CoreEdge Quota Integration;
7. use a server console/test call to read a sandbox quota status;
8. verify CoreEdge Service Request Log shows the correct RetailEdge Service Client/Tenant/Product;
9. revoke the capability and confirm the call is denied;
10. confirm ordinary Sales Invoice and POS workflows remain unchanged because no transaction hook exists yet.

## Next slice

Create a narrow RetailEdge transaction-quota integration only after CoreEdge PR #31 is green.

That PR must name the exact commercial Entitlement Key and prove the counted business event, reserve point, final commit point, rollback/release path, cancellation treatment and POS/Sales Invoice duplicate-prevention rule.