# Eight-minute guided application demo

This block runs at session clock **05:00-13:00**. It includes one genuine,
silent **78.8-second** application clip, not an eight-minute movie. Architecture
and governance explanations live in the deck and presenter commentary.
See [speaker notes](SLIDES-AND-NOTES.md) for the full 15-minute session.

## Before the audience arrives

Complete tenant deployment, consent, connector authorization, publication and
propagation. Verify a fresh pilot user and a nonpilot. Open only relevant
Teams/Copilot, Finance-channel and code windows. Hide account details and
notifications; never display `.env`, access tokens or signed workflow URLs.
Do not expose admin user lists on the projector.

Have the manifest, core decision handler, workflow definition and `.env.example`
ready in the editor. Generate local evidence with `python -m waypoint.demo`.
Prepare the genuine application clip in the event playback system; it is not
distributed in the public code repository. Verify its 78.8-second duration and
local playback without audio/captions or confidential markings.

The recorded Copilot host is **Microsoft 365 Copilot within Teams**. Do not
substitute the unverified standalone Copilot web client. The existing footage
shows the earlier successful workflow; the new final-notification branches
must be rehearsed separately before claiming a newly verified live outcome.

## 00:00-01:10 relative / 05:00-06:10 session

**Existing intelligence and delivery contract**

Show `waypoint/core.py`, then `appPackage/manifest.template.json`.
Point to identity, host scopes and the two job-shaped starters. Show the
already-built ZIP contents: manifest plus two icons, no credentials.

Say: "This is the assurance we already have. The deterministic sample stands
in for the existing Foundry agent; we are not claiming to invoke Foundry here.
The adapter changes how the work arrives, not the business decision rules.
Sarah adds a delivery contract: who the app is, where it can appear and how
Babak starts a useful task. Packaging is not publication, and there are no
secrets in this ZIP."

Fallback: use the prepared source and ZIP, not a live build or download.

## 01:10-02:10 relative / 06:10-07:10 session

**Publication and pilot**

Show a pre-verified, privacy-safe pilot configuration if available; otherwise
refer to the deck's distribution diagram and `.env.example`, explicitly
describing the setup rather than pretending it is a live admin screen.

Say: "Lydia separates availability, install assignment, propagation and sign-in.
A package upload is not all four. The Finance pilot is explicit, and the
backend enforces Finance and approver allowlists independently.
For an attendee deployment those values live in an ignored environment file,
not in the source. Never wait for publication to propagate on stage."

Fallback: show the configuration names and explain their purpose; do not show
real object IDs, group members or administrator credentials.

## 02:10-03:28.8 relative / 07:10-08:28.8 session

**Application in action - play once**

Play `waypoint-application-demo.mp4` for exactly 78.8 seconds.
It shows Teams evidence and escalation, the Finance workflow and Microsoft
365 Copilot within Teams. Let the application be visible; no editorial
slides, added narration or captions inside the media.

Introduce: "Here is Babak's experience in the real host surfaces. Watch for
the contract evidence and the human escalation, not just an answer bubble."

Fallback: if playback fails, perform the rehearsed invoice check and card-button
escalation in Teams. Cap this at the same cue; use prepared local evidence
if the host also fails and state that it is a local fallback.

## 03:28.8-05:00 relative / 08:28.8-10:00 session

**Evidence and the write boundary**

Show INV-1042's card or local prepared evidence: GBP 12,500 invoiced versus
GBP 10,000 expected, GBP 2,500 variance. Point to CAL-C-042 clause 4.2 and
CAL-POL-017 section 3. In code show the decision authorization checks.

Say: "The answer is useful because Babak can inspect why it was flagged.
The contract and policy are explicit synthetic references. This variance
must be escalated; the updated card does not offer an invalid approval.
The server still rejects a forged approval. A recommendation, a button and
authorization are different things. We validate the user, role, nonce,
expiry and whether this request has already been decided.
Typing 'escalate' is not a human card decision.
For a clean invoice the authorized person may record approval, but even
that does not release payment or write to a real ERP."

Fallback: prepared card and the decision handler are sufficient; do not
perform repeated requests just to make counters increase.

## 05:00-06:30 relative / 10:00-11:30 session

**Workflow outcome and recovery**

Show the prepared workflow definition or a run verified before the session.
Trace check -> card -> authenticated responder -> recorded decision -> final
notification. Do not trigger a new hour-long wait on stage.

Say: "The existing approval process can ask the same engine when an invoice
arrives. The event here is synthetic; no ERP is connected. HTTP accepted
means pending review. The card's 'response received' message is not success.
Only a validated, persisted callback allows the final recorded-decision
message. An unknown responder, expired card or failed callback keeps the
workflow failed and the invoice on hold. If the callback succeeded but the
notification failed, inspect the durable record instead of submitting a
second decision. When Teams is unavailable even the failure message may
not arrive, so the run status is essential."

Fallback: show and label the source-defined branches. Do not present static
tests as a live connector run or historical footage as proof of a new release.

## 06:30-07:30 relative / 11:30-12:30 session

**Measure useful work; reproduce the pattern**

Show genuine sample counters from a prepared local rehearsal or verified
backend call, then the repository's quick start and `.env.example`.

Say: "Measure completed checks and human dispositions, not merely installs.
These are sample counters, not an Agent 365 fleet view. Our payment-write
count is zero because the sample has no payment integration.
The repository runs without a tenant first. When ready, configure your
tenant and explicitly provision a dedicated demo environment. The scripts
do not guess an account, and public export excludes local configuration
and tenant-specific packages. Admin approval and sign-in remain real steps."

Fallback: use the genuine output saved during local rehearsal and identify it
as such. Never fabricate usage, savings or tenant policy coverage.

## 07:30-08:00 relative / 12:30-13:00 session

**Outcome**

Say: "The same assurance capability reached the approval moment. Babak got
inspectable evidence and owned the escalation. Sarah did not rebuild the
reasoning; Lydia did not lose the access boundary. The GBP 2,500 discrepancy
is synthetic, not measured savings. That is the publishing pattern:
deliver one useful, governed action where the work already happens."

Return to the lessons slide at **13:00**, leaving exactly two minutes to close.
If running late, shorten source commentary; do not replay or stretch the clip.

## Reset and operational safety

Stop the local server before `python scripts/reset.py`; it removes only the
default local sample database. A configured custom database or deployed Blob
requires a separate, deliberate operator process. Do not reset live state on
stage. New workflow requests require fresh IDs; reuse an ID only when retrying
the same unresolved intake after inspecting its run.

Keep all demonstration records synthetic. Restore a known application version
and create fresh cards before each rehearsal. Obtain applicable event/brand
permissions for assets used outside this source repository.
