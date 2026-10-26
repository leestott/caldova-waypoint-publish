import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch
import os

from aiohttp.test_utils import TestClient, TestServer

from waypoint.config import Settings
from waypoint.core import DemoError, Principal, Waypoint
from waypoint.server import create_app, evidence_message


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Waypoint(Path(self.temp.name) / "test.sqlite3")
        self.babak = Principal("test-babak", True, True)

    def tearDown(self):
        self.temp.cleanup()

    def test_evidence_and_amounts(self):
        evidence = self.engine.evidence("INV-1042")
        self.assertEqual(evidence["variance_pence"], 250000)
        card = self.engine.check("INV-1042", self.babak, "chat")
        self.assertEqual(card["version"], "1.4")
        self.assertIn("CAL-C-042 clause 4.2", json.dumps(card))
        self.assertIn("CAL-POL-017 section 3", json.dumps(card))
        self.assertEqual([a["title"] for a in card["actions"]], ["Escalate"])

    def test_chat_message_has_text_evidence_and_preserves_card_actions(self):
        card = self.engine.check("INV-1042", self.babak, "chat")
        activity = evidence_message(card)
        self.assertEqual(activity.text, card["fallbackText"])
        for value in ("INV-1042", "GBP 12,500.00", "GBP 10,000.00", "GBP 2,500.00",
                      "CAL-C-042 clause 4.2", "CAL-POL-017 section 3",
                      "SYNTHETIC DATA", "No payment released"):
            self.assertIn(value, activity.text)
        self.assertIn("If decision buttons are unavailable", activity.text)
        self.assertEqual(len(activity.attachments), 1)
        self.assertEqual(activity.attachments[0].content_type, "application/vnd.microsoft.card.adaptive")
        self.assertEqual(activity.attachments[0].content, card)
        for action in card["actions"]:
            self.assertNotIn(action["data"]["nonce"], activity.text)
            self.assertNotIn(action["data"]["check_id"], activity.text)

    def test_clean_invoice_text_does_not_claim_variance_or_approval(self):
        card = self.engine.check("INV-1043", self.babak, "chat")
        text = evidence_message(card).text
        self.assertIn("No price variance detected", text)
        self.assertIn("Variance: GBP 0.00", text)
        self.assertIn("Human decision required", text)
        self.assertNotIn("Variance: escalate before approval", text)
        self.assertEqual(self.engine.metrics()["payment_writes"], 0)

    def test_anomaly_list_messages_each_have_their_own_evidence(self):
        cards = self.engine.anomalies_this_week(self.babak)
        self.assertEqual(len(cards), 2)
        for invoice, amount, card in zip(
            ("INV-1042", "INV-1044"), ("GBP 2,500.00", "GBP 3,000.00"), cards
        ):
            activity = evidence_message(card)
            self.assertIn(invoice, activity.text)
            self.assertIn(amount, activity.text)
            self.assertEqual(activity.attachments[0].content, card)

    def test_human_boundary_and_replay(self):
        card = self.engine.check("INV-1042", self.babak, "chat")
        data = card["actions"][0]["data"]
        with self.assertRaisesRegex(DemoError, "blocks approval"):
            self.engine.decide(data["check_id"], data["nonce"], "approve", self.babak)
        self.engine.decide(data["check_id"], data["nonce"], "escalate", self.babak)
        with self.assertRaisesRegex(DemoError, "already"):
            self.engine.decide(data["check_id"], data["nonce"], "escalate", self.babak)
        self.assertEqual(self.engine.metrics()["events"]["human_escalate"], 1)

    def test_clean_invoice_approval_does_not_release_payment(self):
        card = self.engine.check("INV-1043", self.babak, "chat")
        data = card["actions"][0]["data"]
        self.assertIn("No payment", self.engine.decide(data["check_id"], data["nonce"], "approve", self.babak))
        self.assertEqual(self.engine.metrics()["payment_writes"], 0)

    def test_permissions_and_tampered_action(self):
        with self.assertRaisesRegex(DemoError, "pilot"):
            self.engine.check("INV-1042", Principal("outsider", False, False), "chat")
        card = self.engine.check("INV-1042", self.babak, "chat")
        data = card["actions"][0]["data"]
        with self.assertRaisesRegex(DemoError, "approver"):
            self.engine.decide(data["check_id"], data["nonce"], "escalate", Principal("reader", True, False))
        with self.assertRaisesRegex(DemoError, "Invalid"):
            self.engine.decide(data["check_id"], "forged", "escalate", self.babak)

    def test_workflow_idempotency_and_persistence(self):
        request = str(uuid4())
        first = self.engine.check("INV-1044", self.babak, "workflow", request)
        again = Waypoint(self.engine.database).check("INV-1044", self.babak, "workflow", request)
        self.assertEqual(first, again)
        self.assertEqual(self.engine.metrics()["checked_requests"], 1)
        with self.assertRaisesRegex(DemoError, "another request"):
            self.engine.check("INV-1042", self.babak, "workflow", request)

    def test_configured_database_survives_engine_recreation(self):
        location = Path(self.temp.name) / "persistent" / "waypoint.sqlite3"
        with patch.dict(os.environ, {"WAYPOINT_DATABASE": str(location)}):
            engine = Waypoint()
            engine.check("INV-1042", self.babak, "chat")
            self.assertEqual(Waypoint().metrics()["checked_requests"], 1)
            self.assertEqual(engine.database, location)

    def test_week_is_seven_rolling_demo_days(self):
        cards = self.engine.anomalies_this_week(self.babak)
        content = json.dumps(cards)
        self.assertIn("INV-1042", content)
        self.assertIn("INV-1044", content)
        self.assertNotIn("INV-1030", content)

    def test_expired_card(self):
        card = self.engine.check("INV-1042", self.babak, "chat")
        data = card["actions"][0]["data"]
        with self.engine.connection() as db:
            db.execute("UPDATE checks SET created_at='2020-01-01T00:00:00+00:00'")
        with self.assertRaisesRegex(DemoError, "expired"):
            self.engine.decide(data["check_id"], data["nonce"], "escalate", self.babak)


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Waypoint(Path(self.temp.name) / "test.sqlite3")
        self.settings = Settings("local", "x" * 48, "", frozenset(), frozenset(), "")
        self.client = TestClient(TestServer(create_app(self.settings, self.engine)))
        await self.client.start_server()
        self.headers = {"Authorization": "Bearer " + "x" * 48}

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_flow_through_decision(self):
        payload = {"request_id": str(uuid4()), "invoice_id": "INV-1044", "channel_id": "local-finance"}
        response = await self.client.post("/api/invoice-approval", json=payload, headers=self.headers)
        self.assertEqual(response.status, 200)
        result = await response.json()
        data = result["card"]["actions"][0]["data"] | {"responder_oid": "local-babak"}
        response = await self.client.post("/api/workflow-decision", json=data, headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertIn("No payment", (await response.json())["message"])
        response = await self.client.post("/api/workflow-decision", json=data, headers=self.headers)
        self.assertEqual(response.status, 409)

    async def test_workflow_auth_and_channel_scope(self):
        payload = {"request_id": str(uuid4()), "invoice_id": "INV-1042", "channel_id": "wrong-channel"}
        response = await self.client.post("/api/invoice-approval", json=payload)
        self.assertEqual(response.status, 401)
        response = await self.client.post("/api/invoice-approval", json=payload, headers=self.headers)
        self.assertEqual(response.status, 403)

    async def test_invalid_json_and_no_local_bot_bypass(self):
        response = await self.client.post("/api/invoice-approval", data="{", headers=self.headers)
        self.assertEqual(response.status, 400)
        response = await self.client.post("/api/messages", json={})
        self.assertEqual(response.status, 404)

    async def test_unknown_responder_denied(self):
        response = await self.client.post("/api/workflow-decision", json={
            "responder_oid": "forged", "check_id": "fake", "nonce": "fake", "action": "escalate"
        }, headers=self.headers)
        self.assertEqual(response.status, 403)

    async def test_invalid_field_types(self):
        response = await self.client.post("/api/workflow-decision", json={
            "responder_oid": 12, "check_id": "fake", "nonce": "fake", "action": "escalate"
        }, headers=self.headers)
        self.assertEqual(response.status, 400)

    async def test_public_demo_notices_do_not_expose_runtime_secrets(self):
        for route in ("/", "/privacy", "/terms"):
            response = await self.client.get(route)
            self.assertEqual(response.status, 200)
            text = await response.text()
            self.assertIn("Synthetic demonstration", text)
            self.assertNotIn(self.settings.flow_secret, text)
            self.assertIn("demo", text.lower())

    async def test_tenant_endpoint_requires_real_channel_jwt(self):
        tenant, client = str(uuid4()), str(uuid4())
        env = {
            "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID": client,
            "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET": "synthetic-test-only",
            "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID": tenant,
            "AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH__SETTINGS__AZUREBOTOAUTHCONNECTIONNAME": "teams_sso",
        }
        with patch.dict(os.environ, env):
            app = create_app(Settings("tenant", "x" * 48, tenant, frozenset({client}),
                                      frozenset({client}), "finance"), self.engine)
            async with TestClient(TestServer(app)) as client:
                response = await client.post("/api/messages", json={"type": "message", "text": "test"})
                self.assertEqual(response.status, 401)

class ConfigurationTests(unittest.TestCase):
    def test_unknown_mode_fails(self):
        with patch.dict(os.environ, {"WAYPOINT_MODE": "oops", "FLOW_SHARED_SECRET": "x" * 48}):
            with self.assertRaisesRegex(ValueError, "MODE"):
                Settings.load()

    def test_sdk_api_used_by_tenant_adapter_exists(self):
        import inspect
        from microsoft_agents.hosting.core import AgentApplication, TurnContext
        from microsoft_agents.activity import Activity, ActivityTypes
        self.assertIn("auth_handlers", inspect.signature(AgentApplication.activity).parameters)
        self.assertTrue(callable(TurnContext.remove_recipient_mention))
        activity = Activity.model_validate({
            "type": ActivityTypes.message, "text": "Check invoice INV-1042 against contract",
            "from": {"id": "test", "aadObjectId": str(uuid4())},
            "channelData": {"tenant": {"id": str(uuid4())}}
        })
        self.assertTrue(activity.from_property.aad_object_id)
