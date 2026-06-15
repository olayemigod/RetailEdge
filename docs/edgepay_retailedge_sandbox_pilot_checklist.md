# EdgePay + RetailEdge Sandbox Pilot Checklist

This checklist acts as the operational playbook for executing the manual sandbox pilot of the EdgePay and RetailEdge integration.

---

## 1. Prerequisites
- [ ] Ensure `edgepayv1` and `retailedge` apps are installed on the Frappe bench.
- [ ] Verify that roles `EdgePay Admin`, `EdgePay Manager`, `RetailEdge Manager`, and `System Manager` are configured.
- [ ] Obtain sandbox API credentials from the payment provider (e.g. Monnify developer sandbox portal).

---

## 2. Monnify Sandbox Credential Handling
- [ ] **Strict Warning**: **Do NOT commit credentials, keys, or contract codes to the git repository, files, custom scripts, screenshots, or logs.**
- [ ] Store credentials securely using environment variables or fill them directly in the database record:
  - Create/edit an **EdgePay Provider** document named `Monnify Sandbox`.
  - Enter the **API Key** and **Secret Key** in the encrypted password fields.
  - Set the **Contract Code** and **Base URL** (`https://sandbox.monnify.com/api/v1`).
  - Check **Sandbox Mode = 1** and **Enabled = 1**.

---

## 3. Running EdgePay Sandbox Smoke Utility
- [ ] Open the terminal.
- [ ] Run the following command with explicit opt-in environment flags to test sandbox authentication, verification, and checkout URL generation:
  ```bash
  EDGEPAY_RUN_MONNIFY_SANDBOX_SMOKE=1 \
  EDGEPAY_MONNIFY_SANDBOX_API_KEY="your-sandbox-api-key" \
  EDGEPAY_MONNIFY_SANDBOX_SECRET_KEY="your-sandbox-secret-key" \
  EDGEPAY_MONNIFY_SANDBOX_CONTRACT_CODE="your-sandbox-contract-code" \
  bench --site posnext.local run-tests --app edgepayv1 --module edgepayv1.edgepay.tests.test_smoke_utility
  ```
- [ ] Verify that the test output completes with `OK` and prints a generated sandbox Checkout URL.

---

## 4. RetailEdge Source Payment Request & Checkout Simulation
- [ ] Create a **Sales Invoice** or **POS Invoice** in ERPNext/POSNext and submit it.
- [ ] Trigger creation of the **EdgePay Payment Request** mapped to the source document using the SDK or API helper.
- [ ] Retrieve the generated Checkout URL from the response.
- [ ] Open the URL in a browser to load the Monnify Sandbox payment gateway screen.
- [ ] Select a simulated payment method (e.g., Bank Transfer mock) and click pay.

---

## 5. Webhook Simulation & Handoff Processing
- [ ] Simulate or trigger the incoming provider webhook to the whitelisted webhook endpoint:
  - Endpoint: `/api/method/edgepayv1.api.v1.webhook.provider_webhook`
  - Ensure the request headers include a valid signature generated using the configured Secret Key.
- [ ] Verify that the webhook creates/updates the **EdgePay Payment Transaction** and places a new handoff event in the **EdgePay Status Handoff Event** queue.
- [ ] Verify that the background handoff consumer task consumes the event and logs a processed event in the **RetailEdge EdgePay Handoff Log**.

---

## 6. Payment Evidence Review & Submission
- [ ] Open **EdgePay Payment Evidence** under the *EdgePay Review* workspace section.
- [ ] Verify a new record exists with review status `Pending Review`.
- [ ] As an authorized reviewer, click **Mark as Reviewed**.
- [ ] Click **Prepare Draft Payment Entry** to validate the preflight checks and create a draft `Payment Entry`.
- [ ] Click **Submit Payment Entry** to manually submit the document and create accounting ledger postings in ERPNext.

---

## 7. Reconciliation & Match Review Confirmation
- [ ] Open the **EdgePay Reconciliation Readiness** report.
- [ ] Verify that the evidence status has updated to `Ready`.
- [ ] Click **Create Match Review**.
- [ ] Select the **Payment Evidence** and choose the correct matching **Bank Transaction** candidate.
- [ ] Click **Confirm Match Review** to confirm the match review.
- [ ] Verify that the evidence reconciliation status transitions to `Matched` and then to `Reconciled` once matched.

---

## 8. Rollback & Troubleshooting Guidelines

### Status Blocked / Exception
- **Cause**: Mismatched amount/currency, or duplicate references.
- **Rollback / Correction**:
  1. Open the linked `Payment Entry` and check the amount.
  2. If the Payment Entry was incorrect, cancel it (setting docstatus to 2), correct the invoice values, and re-run draft preparation.
  3. Ensure no duplicate confirmed reviews exist for the same reference.

### Stale Handoffs
- **Cause**: Webhook was signature-rejected or task processing failed.
- **Resolution**:
  1. Inspect the **RetailEdge EdgePay Handoff Log** for failure tracebacks (all keys/secrets are redacted in logs).
  2. Re-trigger the processing event manually using the whitelisted API endpoint with authorized accounts manager session.
