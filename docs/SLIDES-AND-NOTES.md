# Publishing agents where work actually happens

Speaker: **Lee Stott, Principal Cloud Advocate, Microsoft**.
Microsoft Ignite 2026 Theatre session: **15:00 including all demos**.
This source companion supports the PowerPoint speaker notes; it is not the deck.
The executable timing contract is [running-order.json](running-order.json).

Use the supplied template's Walkin, Theme 2 Dark and Closing logo layouts,
16:9, Segoe UI Variable Display, blue `#0A6BBA`, green `#4AA647` and white.
Preserve template assets and approved persona names. No confidentiality footer,
guide slides, stock art, replacement portraits or fabricated product icons.
Explanatory material belongs on slides/in presenter notes, not over the application
video. Keep the video silent, caption-free and application-only.

## Running order

| Slide | Session clock | Duration |
|---|---|---|
| 1. Walk-in / outcome | 00:00-00:30 | 0:30 |
| 2. Distribution is the product | 00:30-01:05 | 0:35 |
| 3. Caldova signal and personas | 01:05-01:50 | 0:45 |
| 4. Where work happens | 01:50-02:35 | 0:45 |
| 5. Existing intelligence, new delivery contract | 02:35-03:20 | 0:45 |
| 6. Discoverability and scoped distribution | 03:20-04:05 | 0:45 |
| 7. Governance built in | 04:05-04:45 | 0:40 |
| 8. Demo transition and guided demonstration | 04:45-13:00 | 8:15 |
| 9. Five lessons | 13:00-14:05 | 1:05 |
| 10. Outcome / CTA / closing | 14:05-15:00 | 0:55 |
| **Total** | **00:00-15:00** | **15:00** |

Slide 8 includes 15 seconds of transition and exactly eight minutes of guided
demo. Its 78.8-second video is included, not added. Walk-in delivery and closing
are counted. No separate Q&A allowance is included.

## Slide 1 notes - 00:00-00:30

"Babak leads financial reconciliation at Caldova Pharmaceuticals. His developers
already built an agent that finds invoice anomalies, but a separate browser tab
does not change the approval process. Today we bring that existing capability
to the moment he needs it: before an invoice is approved, not at month-end.
The goal is one governed decision in the flow of work."

Cue: begin the session timer with the opening words. Advance at 00:30.
Keep the title and speaker introduction brief; do not add an agenda.

## Slide 2 notes - 00:30-01:05

"Building an agent is half the job. Delivering it is where value is created.
An endpoint is not a user experience. Babak needs to discover the right action,
sign in without confusion, inspect evidence and make a safe decision where he
already works. Naming, placement and rollout are product decisions, not deployment
plumbing. We are not building another invoice agent today."

Cue: pause on the central statement. Advance at 01:05.

## Slide 3 notes - 01:05-01:50

"Waypoint already has the intelligence: an orchestrator, evidence experts and
a governed write boundary. Our scenario is that it lives outside the daily
approval flow, so anomalies still surface late. Babak Shammas owns financial
reconciliation. Sarah Perez, the app developer, delivers the capability.
Lydia Bauer, the enterprise IT architect, controls who can use it.
Those are supporting roles around one outcome, not three feature tours.
For a reliable, reusable demo, our small backend uses explicitly synthetic,
deterministic evidence instead of invoking Foundry."

Cue: emphasize Babak as the primary persona. No invented adoption statistics.
Advance at 01:50.

## Slide 4 notes - 01:50-02:35

"The assurance logic can be reached from a Teams question, Microsoft 365 Copilot
or the existing approval workflow. Same business capability; different host
experiences. Our recording proves Teams, the Finance channel and Copilot within
Teams. It does not prove every Copilot client. Outlook is a future integration
path here, not a mailbox implementation delivered by this ZIP. Treat host
support as something you verify in your tenant, not an assumption you inherit
from the architecture diagram."

Cue: distinguish demonstrated solid paths from Outlook's architectural path.
Advance at 02:35.

## Slide 5 notes - 02:35-03:20

"Keep the business contract and add a delivery contract. Waypoint owns evidence,
recommendations and permitted writes. The Agents SDK adapts conversations to
that existing logic. The manifest describes identity, names, starter prompts
and supported hosts. The ZIP contains the manifest and icons, never credentials.
Packaging is not publication: hosting, OAuth, administrator approval and
propagation remain real steps. No rebuild means preserving the business
intelligence, not eliminating the work needed to deliver it safely."

Cue: trace existing agent -> adapter/package -> hosts, then the governance rail.
This absorbs the older video's architecture and packaging explanation.
Advance at 03:20.

## Slide 6 notes - 03:20-04:05

"A catalogue entry is not adoption. Give Babak a job-shaped name, description
and starter: Check invoice INV-1042 against contract. Make it easy to return
through pinning or an at-mention where supported. Then separate four concepts:
availability, installation assignment, propagation and authentication.
Publishing a package does not mean all four are done. Lydia starts with Finance,
checks the actual audience and only expands when usage is both useful and safe."

Cue: point to the starter and pilot audience, not a broad product catalogue.
Backend authorization is independent of availability. Advance at 04:05.

## Slide 7 notes - 04:05-04:45

"Governance is in the path from the first check. Review the capability, owner,
data and actions before publication. Entra establishes the user; the backend
still checks Finance membership and the separate approver role. Purview coverage
and Agent 365 inventory or telemetry require their own integration.
Our sample counters are not an Agent 365 dashboard. A recommendation never
authorizes a write, and no path in this sample releases a payment."

Cue: name implemented controls and extension points distinctly.
Advance at 04:45.

## Slide 8 notes - 04:45-13:00

Transition, 04:45-05:00:
"Follow one invoice from signal to evidence to a human escalation. Sarah
provides the delivery contract, Lydia scopes access and Babak acts on the
evidence. All records you will see are synthetic."

At **05:00**, switch to the prepared application/code windows. Use the detailed
[demo script](DEMO-SCRIPT.md), with these absolute checkpoints:

| Session clock | Presenter action |
|---|---|
| 05:00-06:10 | Show existing assurance logic and manifest; no secrets |
| 06:10-07:10 | Explain prepared publication and pilot controls; no live propagation wait |
| 07:10-08:28.8 | Play `waypoint-application-demo.mp4` once: 78.8 seconds |
| 08:28.8-10:00 | Inspect evidence and server-side decision boundary |
| 10:00-11:30 | Explain workflow receipt, validation, final outcome and recovery |
| 11:30-12:30 | Show genuine sample measurements and redeployment entry point |
| 12:30-13:00 | Restate the outcome and return to slides |

Do not describe the clip as eight minutes or replay it to fill time. The clip
has no narration/captions; the presenter may introduce the scenes, then let the
real application interaction remain visible. Use no confidential older recording.

The current clip is a separate local media asset; this companion does not claim
it is embedded in PowerPoint. Prepare playback on the presentation machine.
If embedded later, preserve the same cue and duration.

Hard stop at **13:00**: return to slide 9. If behind, shorten code inspection
and commentary; never skip the human decision or misrepresent an unverified result.

## Slide 9 notes - 13:00-14:05

"Five lessons. First, design for the host: compact evidence and an action card,
with readable text when a client does not render the attachment as expected.
Second, rehearse authentication before the first useful question, with a fresh
pilot user rather than only the developer's account. Third, keep the human
write boundary on the server; a button is not a security control.
Fourth, measure completed checks and human dispositions, not just installations.
Those counters are operational evidence, not invented fleet coverage.
Finally, version the manifest and backend together, validate both supported
package variants, pilot releases and plan rollback. Distribution needs the
same engineering discipline as the intelligence behind it."

Cue: no demo reopening. Advance at 14:05.

## Slide 10 notes - 14:05-15:00

"Babak did not get another destination to visit. The assurance capability met
him at the approval moment, with evidence he could inspect and an escalation
he owned. The GBP 2,500 variance is synthetic, not a claim of measured savings.
Start with one workflow, one useful prompt and one governed pilot.
The sample includes local setup, tenant configuration, a deployment entry point
and the human decision boundary, so you can reproduce the pattern in your own
environment. Keep the reasoning you have and measure whether people complete
the job more safely. Thank you."

Cue: show [the public sample](https://github.com/leestott/caldova-waypoint-publish)
and `github.com/caldova`.
Use the direct Microsoft documentation links in VERIFICATION.md rather than
inventing an aka.ms redirect. Preserve the template closing logo. Stop at 15:00.

## Rehearsal

The JSON timing check proves the planned budget totals 900 seconds, not that
an unrehearsed delivery will meet it. Run through Presenter View with the actual
machine, display, playback method and a visible elapsed timer. All network
preparation and propagation must finish before the session starts.
