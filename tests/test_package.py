import unittest
from uuid import uuid4

from scripts.package import DEMO, render


class ManifestTests(unittest.TestCase):
    def test_manifest_declares_same_bot_for_teams_and_copilot(self):
        manifest = render(DEMO)
        self.assertEqual(manifest["manifestVersion"], "1.30")
        self.assertEqual(manifest["bots"][0]["botId"],
                         manifest["copilotAgents"]["customEngineAgents"][0]["id"])
        self.assertEqual(manifest["webApplicationInfo"]["id"], manifest["bots"][0]["botId"])
        scopes = manifest["bots"][0]["scopes"]
        self.assertTrue({"personal", "team", "copilot"} <= set(scopes))

    def test_prompts_are_explicit_not_implied_slash_commands(self):
        manifest = render(DEMO)
        commands = manifest["bots"][0]["commandLists"][0]["commands"]
        self.assertEqual([command["type"] for command in commands], ["prompt", "prompt"])
        self.assertEqual([command["prompt"] for command in commands], [
            "Check invoice INV-1042 against contract", "Show anomalies this week"
        ])

    def test_compatibility_package_keeps_identity_and_usable_command_starters(self):
        current = render(DEMO)
        compatible = render(DEMO, compatibility=True)
        self.assertEqual(compatible["manifestVersion"], "1.24")
        self.assertIn("/v1.24/", compatible["$schema"])
        self.assertEqual(compatible["id"], current["id"])
        self.assertEqual(compatible["copilotAgents"], current["copilotAgents"])
        commands = compatible["bots"][0]["commandLists"][0]["commands"]
        self.assertEqual([item["title"] for item in commands], [
            "Check invoice INV-1042", "Show anomalies this week",
        ])
        self.assertTrue(all("prompt" not in item and "type" not in item for item in commands))

    def test_missing_and_injected_configuration_fail(self):
        with self.assertRaisesRegex(ValueError, "BOT_ID"):
            render(DEMO | {"BOT_ID": ""})
        with self.assertRaises(ValueError):
            render(DEMO | {"APP_ID": 'invalid"ID'})
        for url in ("http://waypoint.example.com", "https://user:secret@waypoint.example.com",
                    "https://waypoint.example.com?secret=x"):
            with self.assertRaisesRegex(ValueError, "HTTPS origin"):
                render(DEMO | {"APP_BASE_URL": url})

    def test_environment_guid_values_render_without_placeholder_leakage(self):
        manifest = render(DEMO | {"APP_ID": str(uuid4()), "BOT_ID": str(uuid4())})
        self.assertNotIn("{{", str(manifest))
