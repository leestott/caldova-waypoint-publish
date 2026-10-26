# Verification and honest demonstration boundaries

This ledger distinguishes code, earlier tenant observations and acceptance work
still required. It is not a compliance assessment or a claim of production readiness.

## Client and integration matrix

| Surface or capability | Evidence and boundary |
|---|---|
| Teams chat | Earlier pilot rehearsal exercised discovery, install, starter, evidence and human card-button escalation |
| Microsoft 365 Copilot within Teams | Evidence text plus card, starter and card-button escalation exercised |
| Standalone Microsoft 365 Copilot web client | Attempt returned a blank response; not verified |
| Finance channel workflow | Earlier synthetic run verified check, card, authenticated responder and recorded escalation |
| New final outcome notification branches | Covered by source/structure tests; require acceptance in the target tenant |
| v1.24 package | Earlier tenant accepted compatibility package; local/CI validate official schema |
| v1.30 package | Official schema validation does not guarantee acceptance in every tenant |
| Interactive sign-in | Exercised; seamless SSO is not verified |
| Outlook/mailbox | Not implemented or demonstrated |
| Foundry/Fabric/OneLake | Reference architecture only; local deterministic seed replaces these services |
| Agent 365/Purview | Separate integration work, not provided by the manifest or sample counters |
| ERP and payments | Deliberately absent; zero payment execution |

Earlier observations are not a fresh acceptance test of a new version or a
different tenant. Record your own version, host, date and results privately.
No operator identifiers, private URLs or tenant footage belong in this source.

## Primary references

| Topic | Primary source |
|---|---|
| Custom engine agents and Agents SDK | [Create/deploy Agents SDK](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/create-deploy-agents-sdk) |
| Toolkit | [Microsoft 365 Agents Toolkit](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/overview-agents-toolkit) |
| Manifest schema | [v1.30](https://developer.microsoft.com/json-schemas/teams/v1.30/MicrosoftTeams.schema.json), [v1.24](https://developer.microsoft.com/json-schemas/teams/v1.24/MicrosoftTeams.schema.json) |
| Starter prompts | [Prompt starters](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/prompt-starters) |
| SDK authentication | [OAuth configuration](https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/agent-oauth-configuration) |
| Agent requests | [Admin requests](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-requests) |
| Inventory | [Registry](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-registry-overview) |
| Agent 365 vs Agents SDK | [Agent 365 SDK](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk) |
| Fleet telemetry | [Microsoft OpenTelemetry](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry) |
| Data protection | [Purview for Agent 365](https://learn.microsoft.com/en-us/purview/ai-agent-365) |
| Teams workflow operations | [Teams connector](https://learn.microsoft.com/en-us/connectors/teams/) |
| Host UX | [Custom engine UX](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/ux-custom-engine-agent) |
| Reference application | [Caldova Waypoint](https://github.com/caldova/waypoint) |

Documentation and product availability change. Verify current licensing,
preview status, client support and approved announcement wording before the event.
Do not imply that a capability was announced at Ignite 2026 without an approved
source. Microsoft 365 Agents SDK and Microsoft Agent 365 SDK are different tools.

## Public-release checks

Unit tests exercise evidence, money calculations, role/tenant boundaries, nonce
expiry, replay protection, HTTP authentication and durable state behavior.
Additional tests cover deployment configuration, source export and workflow
outcome wiring. CI validates both manifest schemas on Python 3.11 and 3.13.

The public-source check rejects common credential patterns and known private
configuration values without printing them. Export excludes `.env`, runtime
state, operator records and tenant packages by default. This does not replace
secret scanning, dependency review, penetration testing or legal clearance.

MIT covers the authored sample as described in [NOTICE](../NOTICE.md), not
Microsoft event assets or trademarks. No persona portraits or deck templates
are shipped. Exact Caldova persona names are preserved; financial records
are newly authored synthetic examples, not real business records.
