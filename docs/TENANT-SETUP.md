# Deploy into your own tenant

Use a dedicated **synthetic demonstration** environment. Nothing in this source
identifies the speaker's tenant or grants access to it. Read [NOTICE](../NOTICE.md)
and the [verification boundaries](VERIFICATION.md) first.

## Prerequisites and costs

- Python 3.11+, PowerShell and Azure CLI; local setup completed.
- A Microsoft 365 tenant with Teams and the applicable Copilot entitlement.
- A supported Azure region and quota for Container Apps, ACR and Storage.
- An operator permitted to create the resource group, managed identity and role
  assignments, plus directory applications, groups and a private Team.
- An administrator for enterprise-app assignment, consent, custom-app publication
  and connector authorization. A single account need not hold permanent broad
  privileges; follow your organization's least-privilege/PIM process.

Container Apps runs one 0.5-vCPU/1-GiB replica continuously for reliable rehearsal.
ACR Basic, Storage and Logic Apps also incur charges. Pricing varies by region and
subscription. Review Azure pricing and set a budget before provisioning.

## Configure, without committing identifiers or secrets

Run `.\scripts\setup.ps1`, then edit the generated **ignored** `.env` locally.
It must contain your own values for:

| Setting | Meaning |
|---|---|
| `TENANT_ID` | Your Entra tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | Subscription in that tenant |
| `DEPLOYMENT_USER_PRINCIPAL_NAME` | Exact Azure CLI operator username |
| `AZURE_RESOURCE_GROUP` | A dedicated group, not a shared production group |
| `AZURE_LOCATION` | Region such as `eastus`, subject to your quota |
| `DEPLOYMENT_PREFIX` | 3-10 lowercase letters/digits/hyphens, beginning with a letter |
| `FINANCE_PILOT_OIDS` | Comma-separated user object IDs; blank means the operator only |
| `FINANCE_APPROVER_OIDS` | Subset of pilots; blank means the operator only |

Names derive from the prefix; global storage/registry names include a stable
target hash. `.env.example` lists optional overrides. Set both Finance lists
explicitly when the operator is not an end-user pilot. Finance Team membership
allows only the configured pilots plus its operator owner. Existing broader
membership fails rather than silently removing people or exposing new cards.

Leave `WAYPOINT_MODE=local` for local rehearsal. Deployment sets the Azure
runtime's tenant mode separately. Azure bot/flow secrets are generated and
stored as Container Apps secrets, never placed in source or deployment JSON.
The local `FLOW_SHARED_SECRET` is not automatically the deployed credential.
`.env` is a development configuration file, **not a production vault**.

Sign in interactively using `az login --tenant YOUR_TENANT_ID`, then select your
subscription. Replace the command's illustrative name with your actual configured
value; do not paste credentials into commands. The scripts reject an operator
or tenant mismatch instead of switching accounts behind your back.

## Provision

```powershell
.\scripts\deploy.ps1 -Provision
```

The explicit switch acknowledges resource creation. The script stops at a failed
phase and saves non-secret progress in ignored `dist\deployment.json`.
It runs, in order:

1. Resource group and provider registration.
2. Single-tenant app identity and Graph sign-in scope.
3. Finance security group, enterprise-app assignment and private Team/channel.
4. Container environment, private registry, storage and scoped managed identity.
5. Remote container build and one-replica runtime configuration.
6. Azure Bot, Teams channel and federated OAuth connection.
7. Schema-validated v1.24 tenant package.
8. HTTP-triggered Logic App and Teams connection.

Preserve `dist\deployment.json` for retries and cleanup. Do not delete it to
silence a mismatch. Changing the tenant, subscription, resource group, region or
resource names requires a fresh checkout/environment. Untracked app registrations
with the same name are not automatically taken over.

Individual phases are available through `scripts\deploy_azure.py`,
`scripts\deploy_container.py` and `scripts\deploy_workflow.py`; inspect the failed
phase before resuming. Do not rerun uncertain creation requests blindly.
Some directory operations and propagation need administrator intervention.

## Finish the interactive Microsoft steps

Authorize the new Teams API connection in Azure with the intended account.
That account must be allowed to post cards in the configured Finance channel.
The Workflows/Power Automate app and connectors must be allowed by Teams policy.
Complete required application consent through the organization's approved process.

Upload `dist\tenant\waypoint.zip` through your supported custom-app/admin submission
route. Review identity, URLs, permissions and actions before approval. Restrict
**availability and installation assignment** to the Finance pilot and verify the
result immediately; some admin paths initially apply broad defaults. Backend
allowlists remain independent even when catalogue availability is wrong.

The default template is v1.30. The orchestrator uses v1.24 compatibility because
that version was accepted in the rehearsal tenant. To build v1.30 explicitly:

```powershell
.\.venv\Scripts\python.exe scripts\deploy_azure.py package
```

Compatibility converts typed prompts to command-menu starters; do not promise
identical starter UI. A valid ZIP is not proof of publication, propagation,
installation, host support or SSO. Test a fresh pilot user and a nonpilot.
The runtime includes an SDK OAuth handler and Graph `/me` verification; a
manifest's `webApplicationInfo` alone does not implement sign-in.

## Verify the application and workflow

After HTTPS readiness and consent:

```powershell
.\.venv\Scripts\python.exe scripts\verify_deployment.py
.\.venv\Scripts\python.exe scripts\tenant_invoice_request.py --invoice INV-1044
```

The first command performs synthetic API checks, rejects unauthorized activity,
checks replay/channel/role guards and prints sample counters, not secrets.
It does not automate a successful human Finance decision.
The second retrieves the signed workflow URL in memory and prints a request/run
ID, not that URL. HTTP 202 means **accepted pending review**, not approved.

In the Finance channel inspect the evidence, then click **Escalate**. Require
successful responder verification, `Record_human_decision`, and
`Notify_decision_recorded` in the same run. The receipt text is not a final
acknowledgment. The final message must name the recorded decision.
Repeat with INV-1043 for a clean invoice: an authorized person may approve
the sample disposition, but no payment or ERP write is executed.

Test Teams chat and Microsoft 365 Copilot **within Teams** separately. Other
Copilot clients and Outlook are not covered by the earlier rehearsal.
Type an invoice check and use the card button; typing `escalate` alone does
not authorize a decision.

## Failure and recovery

| Observation | Required response |
|---|---|
| Trigger/check not confirmed | Keep invoice on hold; inspect run before retrying the same request ID |
| Card rejected, failed or expired | Repair connector/permissions; request a fresh card after confirming no decision |
| Unverified responder or request binding | No callback; use an authorized Finance approver and a fresh request |
| Callback rejected or timed out | Decision is **not confirmed**; inspect durable state before another request |
| Callback succeeded but final message failed | Decision may already be recorded; repair notification, do not submit a second decision |
| Nonce expired or request already decided | Server rejects it; never bypass the write boundary |

Failure notifications are best effort if Teams itself is unavailable; workflow
failure remains visible in Azure. A success-shaped channel receipt never
overrides callback status. Secure inputs/outputs can conceal diagnostic details;
authorized operators should use run action status and trusted backend state
without exporting secrets or actor identities.

The one-hour card window can expire. Do not use a paused overnight card as a
stage fallback. Generate fresh requests and rehearse before the session.

## Release, rotation and removal

Version the manifest and backend together. Run the tests and both package builds;
deploy through a pilot and verify every promised host before expanding. Keep
previous artifacts and a deliberate rollback plan. Rebuilding code does not
automatically update the catalogue package.

The generated host credential expires after 90 days. Rotate using your approved
Entra/Azure process, update the runtime secret, restart/rehearse sign-in and
remove the old credential only after verification. Rotate the flow credential
in both runtime and workflow together.

For teardown, first unpublish/uninstall the app and stop new workflow intake.
Inspect saved resource IDs before deleting the dedicated Azure resource group.
Then separately remove the dedicated directory app/service principal, pilot
group and private Team according to retention policy. Resource-group deletion
does not remove Microsoft 365 directory objects. No automatic destructive
cleanup is provided. Never delete shared resources based on their names alone.
