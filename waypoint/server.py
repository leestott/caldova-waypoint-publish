import hmac
import json
import logging
import os
import re
from uuid import UUID

from aiohttp import ClientSession, ClientTimeout, web

from .config import Settings
from .core import DemoError, Waypoint

LOG = logging.getLogger("waypoint")


def evidence_message(card: dict):
    from microsoft_agents.activity import Attachment
    from microsoft_agents.hosting.core import MessageFactory

    # Some hosts omit attachment-only responses; keep the evidence readable.
    return MessageFactory.attachment(
        Attachment(content_type="application/vnd.microsoft.card.adaptive", content=card),
        text=card["fallbackText"],
    )


@web.middleware
async def errors(request: web.Request, handler):
    try:
        return await handler(request)
    except DemoError as exc:
        LOG.warning("request_rejected path=%s status=%d reason=%s", request.path, exc.status, exc)
        return web.json_response({"error": str(exc)}, status=exc.status)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        LOG.warning("invalid_request path=%s type=%s", request.path, type(exc).__name__)
        return web.json_response({"error": "Invalid request fields or JSON."}, status=400)


def create_app(settings: Settings | None = None, engine: Waypoint | None = None) -> web.Application:
    settings = settings or Settings.load()
    engine = engine or Waypoint()
    app = web.Application(middlewares=[errors], client_max_size=32768)

    async def health(request):
        return web.json_response({"status": "ready", "mode": settings.mode, "backend": "synthetic"})

    async def information(request):
        notices = {
            "/": (
                "Waypoint | Caldova Pharmaceuticals | Synthetic demonstration\n"
                "Synthetic invoice-assurance demonstration. Use the approved Teams/Copilot app.\n"
                "No real customer data, Foundry inference, ERP writes or payment execution.\n"
            ),
            "/privacy": (
                "Waypoint demo privacy notice | Synthetic demonstration\n"
                "For the restricted demonstration pilot only. Microsoft sign-in verifies the caller. "
                "The service processes synthetic invoices and records human decision object IDs "
                "and hashed-actor usage events. Access tokens and prompts are not written to the "
                "demo database. Azure/Bot/Teams platform logs and tenant retention policies also apply. "
                "This demo must not receive real customer or sensitive data. "
                "The tenant administrator controls access, retention and deletion. "
                "This notice is not an enterprise privacy policy or public-production clearance.\n"
            ),
            "/terms": (
                "Waypoint demo terms | Synthetic demonstration\n"
                "Restricted synthetic-data evaluation only; not a production financial service. "
                "Results and approvals are simulated, require human review and never release payment. "
                "Do not rely on the demonstration for financial, regulatory or operational decisions. "
                "Distribution outside the approved pilot requires separate organizational clearance.\n"
            ),
        }
        return web.Response(text=notices[request.path], content_type="text/plain")

    def require_flow(request):
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.flow_secret}"
        if not hmac.compare_digest(auth.encode(), expected.encode()):
            raise DemoError("Workflow credential missing or invalid.", 401)

    async def fields(request, names):
        data = await request.json()
        if not isinstance(data, dict) or any(
            not isinstance(data.get(name), str) or not data[name].strip()
            for name in names
        ):
            raise DemoError("Required request fields must be nonempty strings.")
        return data

    async def invoice_request(request):
        require_flow(request)
        data = await fields(request, ("channel_id", "request_id", "invoice_id"))
        channel = "local-finance" if settings.mode == "local" else settings.channel_id
        if data["channel_id"] != channel:
            raise DemoError("Workflow target is outside the approved Finance channel.", 403)
        UUID(data["request_id"])
        # The workload can read the Finance corpus, but cannot make a human decision.
        from .core import Principal
        card = engine.check(data["invoice_id"], Principal("approval-workflow", True, False),
                            "workflow", data["request_id"])
        return web.json_response({"card": card, "request_id": data["request_id"]})

    async def workflow_decision(request):
        require_flow(request)
        data = await fields(request, ("responder_oid", "check_id", "nonce", "action"))
        # Trust boundary: only the configured flow may attest the connector's responder OID.
        actor = settings.principal(data["responder_oid"])
        result = engine.decide(data["check_id"], data["nonce"], data["action"], actor)
        return web.json_response({"message": result})

    async def telemetry(request):
        require_flow(request)
        return web.json_response(engine.metrics())

    app.router.add_get("/health", health)
    for route in ("/", "/privacy", "/terms"):
        app.router.add_get(route, information)
    app.router.add_post("/api/invoice-approval", invoice_request)
    app.router.add_post("/api/workflow-decision", workflow_decision)
    app.router.add_get("/api/telemetry", telemetry)

    if settings.mode == "tenant":
        install_agent(app, settings, engine)
    return app


def install_agent(app: web.Application, settings: Settings, engine: Waypoint) -> None:
    from microsoft_agents.activity import ActivityTypes, load_configuration_from_env
    from microsoft_agents.authentication.msal import MsalConnectionManager
    from microsoft_agents.hosting.aiohttp import (
        CloudAdapter, jwt_authorization_middleware, start_agent_process,
    )
    from microsoft_agents.hosting.core import (
        AgentApplication, Authorization, MemoryStorage, MessageFactory, TurnContext,
    )

    config = load_configuration_from_env(os.environ)
    storage = MemoryStorage()
    connections = MsalConnectionManager(**config)
    adapter = CloudAdapter(connection_manager=connections)
    authorization = Authorization(storage, connections, **config)
    agent = AgentApplication(
        storage=storage, adapter=adapter, authorization=authorization, **config
    )

    async def actor_for(context):
        activity = context.activity
        channel = activity.channel_data or {}
        tenant = channel.get("tenant", {}).get("id", "")
        if tenant.lower() != settings.tenant_id:
            raise DemoError("Activity is outside the configured tenant.", 403)
        response = await agent.auth.get_token(context, "GRAPH")
        if response is None or not response.token:
            raise DemoError("Sign-in required. Retry after completing the Microsoft sign-in.", 401)
        async with ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.get(
                "https://graph.microsoft.com/v1.0/me?$select=id",
                headers={"Authorization": f"Bearer {response.token}"},
            ) as result:
                if result.status != 200:
                    raise DemoError("Unable to verify the signed-in user with Microsoft Graph.", 401)
                profile = await result.json()
        oid = str(profile["id"]).lower()
        if oid != str(activity.from_property.aad_object_id).lower():
            raise DemoError("Signed-in user does not match the activity sender.", 403)
        return settings.principal(oid)

    @agent.activity(ActivityTypes.message, auth_handlers=["GRAPH"])
    async def message(context, state):
        try:
            principal = await actor_for(context)
            data = context.activity.value
            if isinstance(data, dict) and "action" in data:
                result = engine.decide(data["check_id"], data["nonce"], data["action"], principal)
                await context.send_activity(MessageFactory.text(result))
                return
            text = TurnContext.remove_recipient_mention(context.activity) or context.activity.text or ""
            if "show anomalies this week" in text.lower():
                cards = engine.anomalies_this_week(principal)
            else:
                match = re.search(r"\bINV-\d{4}\b", text, re.IGNORECASE)
                if not match:
                    await context.send_activity(MessageFactory.text(
                        "Check invoice INV-1042 against contract, or: Show anomalies this week."
                    ))
                    return
                cards = [engine.check(match.group().upper(), principal, "chat")]
            for card in cards:
                await context.send_activity(evidence_message(card))
        except DemoError as exc:
            LOG.warning("agent_request_rejected status=%d reason=%s", exc.status, exc)
            await context.send_activity(MessageFactory.text(str(exc)))

    async def agent_error(context, error):
        LOG.error("agent_turn_failed type=%s", type(error).__name__)
        await context.send_activity(MessageFactory.text(
            "Waypoint could not complete this request. No decision was recorded; retry or contact the demo operator."
        ))

    adapter.on_turn_error = agent_error

    async def messages(request):
        # Apply SDK channel JWT validation only to the Bot endpoint, not flow endpoints.
        return await jwt_authorization_middleware(
            request, lambda req: start_agent_process(req, agent, adapter)
        )

    app["agent_configuration"] = connections.get_default_connection_configuration()
    app["agent_app"] = agent
    app["adapter"] = adapter
    app.router.add_post("/api/messages", messages)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = Settings.load()
    if settings.mode == "local" and os.getenv("HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise ValueError("Local simulation must bind to loopback only.")
    web.run_app(create_app(settings), host=os.getenv("HOST", "127.0.0.1"),
                port=int(os.getenv("PORT", "3978")))
