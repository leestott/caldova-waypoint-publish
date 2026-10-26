# caldova-waypoint-publish

**A synthetic, MIT-licensed Microsoft 365 Agents SDK publishing sample.**

Help **Babak Shammas, Financial Reconciliation Lead**, catch an invoice anomaly
at approval rather than month-end. **Sarah Perez, App Developer (Technology)**,
publishes the capability. **Lydia Bauer, Enterprise IT Architect**, scopes its use.

This deterministic stand-in for [Caldova Waypoint](https://github.com/caldova/waypoint)
keeps evidence checks separate from human decisions. It does **not** invoke
Foundry, Fabric, OneLake, an ERP or a payment system. The sample records a human
disposition, not a payment authorization. See [rights and boundaries](NOTICE.md).

## Run locally without a tenant

Requires Python 3.11+ and PowerShell, with internet access to PyPI and Microsoft's
manifest schemas. From the repository root:

```powershell
.\scripts\setup.ps1
```

This creates `.venv`, preserves any existing `.env`, initializes a random local
workflow credential, runs tests, validates a demo manifest and rehearses synthetic
evidence and escalation. It does not create Azure resources or change tenant policy.
The generated `dist\demo\waypoint-DEMO-NOT-FOR-UPLOAD.zip` cannot be uploaded
to a tenant. Generated icons are original Waypoint monograms, not Microsoft logos.

For an HTTP rehearsal use two terminals:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m waypoint.server
# Terminal 2
.\.venv\Scripts\python.exe scripts\workflow_request.py
```

Local readiness is `http://127.0.0.1:3978/health`. Local mode deliberately has no
`/api/messages` bot route and does not post to Teams. On other operating systems,
create a Python virtual environment, install `requirements.txt`, then run
`python scripts/initialize.py`, `python -m unittest discover -s tests`,
`python scripts/package.py --demo` and `python -m waypoint.demo`.

## Deploy to your tenant

Follow [TENANT-SETUP.md](docs/TENANT-SETUP.md), configure **your own** account,
subscription, tenant and resource names in the ignored `.env`, then explicitly run:

```powershell
.\scripts\deploy.ps1 -Provision
```

This creates billable Azure resources and directory objects. Connector sign-in,
admin consent, app submission and pilot publication remain interactive administrator
steps. Neither a package nor a deployment grants automatic access to all hosts.
Do not use real invoices or publish this sample organization-wide.

| Included | Boundary |
|---|---|
| Microsoft 365 Agents SDK bot adapter | Existing deterministic assurance logic, not Foundry inference |
| v1.30 manifest and v1.24 compatibility build | Validate the accepted schema and experience in your tenant |
| Evidence text plus Adaptive Cards | Teams and Microsoft 365 Copilot within Teams were exercised; standalone Copilot remains unverified |
| Entra sign-in and Finance allowlists | Interactive sign-in exercised; seamless SSO requires your own rehearsal |
| Synthetic approval HTTP trigger and Teams connector | No real invoice system is connected |
| Verified responder, nonce, expiry and replay checks | Variance can only be escalated; clean invoices also offer human approval |
| Explicit workflow outcome/failure notification paths | New final-notification paths require a connector acceptance test in your tenant |
| SQLite counters and leased private Blob snapshots | Not Agent 365 telemetry, Purview integration or a production database |

Outlook is an architectural extension, not an implemented mailbox or notification
integration. Product availability and host behavior depend on licences, policy and
rollout. See the [verification ledger](docs/VERIFICATION.md).

## Session resources

The session is **15 minutes including the demo**: five-minute setup, eight-minute
guided demonstration and two-minute wrap-up. The 78.8-second silent application
recording sits inside the guided demonstration, not in addition to it.
Tenant recordings and Microsoft event assets are not distributed in this repository.

- [Speaker notes and 15-minute running order](docs/SLIDES-AND-NOTES.md)
- [Eight-minute demo, fallback and recovery script](docs/DEMO-SCRIPT.md)
- [Tenant deployment and removal](docs/TENANT-SETUP.md)
- [Claims, client scope and verification](docs/VERIFICATION.md)

`data\seed.json` is the entire synthetic corpus. INV-1042 has a GBP 2,500
discrepancy; this is not proven savings. "This week" means trailing seven
synthetic days from `age_days`, not the wall-clock calendar week.

## Validate and distribute source

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\package.py --demo
.\.venv\Scripts\python.exe scripts\package.py --demo --compatibility
.\.venv\Scripts\python.exe scripts\check_public.py
.\.venv\Scripts\python.exe scripts\export.py dist\public
```

CI covers both schema variants on Python 3.11 and 3.13. Public export contains
portable source, licence and workflow, not `.env`, deployment state, live tenant
packages, videos or private operator records. `--include-tenant-package` is an
explicit **private operator export** only; never attach that package as generic
public sample code. Static release checks are not a full security certification.

For isolated stage branches, `python scripts/prepare_branches.py` creates
`demo/01-existing` and `demo/02-publish` in a separate `dist` repository.
It does not change this checkout or publish anything.

## Operational limits

The server is single-instance. Azure uses a managed identity, a private Blob and
an exclusive lease for tiny SQLite snapshots. Failed persistence is an error,
not an acknowledged decision. OAuth conversation state is in memory; restarting
can require sign-in. Use a managed transactional database, rate limiting, secret
rotation and central monitoring before considering any production adaptation.

The workflow's shared credential authorizes a trusted workload to attest the
Teams connector responder. Secure flow inputs/outputs, restrict owners, use TLS
and never accept browser-supplied identity as an authenticated user. Prefer
Entra-protected APIs with validated claims for production. Pilot catalogue
availability is separate from backend authorization; keep group membership,
Team membership and both runtime allowlists aligned.
