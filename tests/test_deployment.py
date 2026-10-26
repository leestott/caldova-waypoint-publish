import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True):
    import deploy_azure
    import deploy_workflow
    from deployment_config import DeploymentSettings, finance_oids

ENV = {
    "PYTHON_DOTENV_DISABLED": "1",
    "AZURE_SUBSCRIPTION_ID": "11111111-1111-4111-8111-111111111111",
    "TENANT_ID": "22222222-2222-4222-8222-222222222222",
    "DEPLOYMENT_USER_PRINCIPAL_NAME": "operator@example.com",
    "AZURE_RESOURCE_GROUP": "rg-synthetic",
    "AZURE_LOCATION": "eastus",
}
OWNER = "33333333-3333-4333-8333-333333333333"
PILOT = "44444444-4444-4444-8444-444444444444"


class DeploymentTests(unittest.TestCase):
    def settings(self, **changes):
        with patch.dict(os.environ, ENV | changes, clear=True):
            return DeploymentSettings.load()

    def test_explicit_target_and_deterministic_names(self):
        first = self.settings()
        first.validate()
        self.assertEqual(first.names, self.settings().names)
        other = self.settings(AZURE_RESOURCE_GROUP="rg-another")
        self.assertNotEqual(first.names["AZURE_STORAGE_ACCOUNT"], other.names["AZURE_STORAGE_ACCOUNT"])
        self.assertNotEqual(first.names["AZURE_CONTAINER_REGISTRY"], other.names["AZURE_CONTAINER_REGISTRY"])

    def test_missing_and_invalid_target_fail_before_network(self):
        for key in ("AZURE_SUBSCRIPTION_ID", "TENANT_ID", "DEPLOYMENT_USER_PRINCIPAL_NAME",
                    "AZURE_RESOURCE_GROUP", "AZURE_LOCATION"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.settings(**{key: ""}).validate()
        for changes in ({"DEPLOYMENT_PREFIX": "Bad Name"}, {"AZURE_STORAGE_ACCOUNT": "bad-name"},
                        {"AZURE_BOT_NAME": "bad name"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.settings(**changes).validate()

    def test_blank_overrides_preserve_defaults(self):
        self.assertEqual(self.settings(AZURE_BOT_NAME="").names["AZURE_BOT_NAME"], "waypoint-bot")
        self.assertEqual(self.settings(AZURE_BOT_NAME="custom-bot").names["AZURE_BOT_NAME"], "custom-bot")

    def test_finance_defaults_and_approver_subset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(finance_oids(OWNER), ([OWNER], [OWNER]))
        with patch.dict(os.environ, {"FINANCE_PILOT_OIDS": OWNER, "FINANCE_APPROVER_OIDS": PILOT}, clear=True):
            with self.assertRaisesRegex(ValueError, "subset"):
                finance_oids(OWNER)
        with patch.dict(os.environ, {"FINANCE_PILOT_OIDS": "invalid"}, clear=True):
            with self.assertRaises(ValueError):
                finance_oids(OWNER)

    def test_saved_state_rejects_target_and_resource_name_changes(self):
        config = self.settings()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "deployment.json"
            with patch.object(deploy_azure, "CONFIG", config), patch.object(deploy_azure, "STATE", path):
                self.assertEqual(deploy_azure.state(), config.identity())
                path.write_text(json.dumps(config.identity() | {"resource_names": config.names}))
                deploy_azure.state()
                path.write_text(json.dumps(config.identity() | {"tenant_id": OWNER}))
                with self.assertRaisesRegex(RuntimeError, "different target"):
                    deploy_azure.state()
                path.write_text(json.dumps(config.identity() | {"resource_names": {}}))
                with self.assertRaisesRegex(RuntimeError, "Resource names"):
                    deploy_azure.state()

    def test_untracked_existing_app_is_not_modified(self):
        with patch.object(deploy_azure, "CONFIG", self.settings()), patch.object(
            deploy_azure, "api", return_value=({"value": [{"id": "untracked"}]}, {})
        ) as api:
            with self.assertRaisesRegex(RuntimeError, "untracked app"):
                deploy_azure.provision_identity({}, OWNER)
            self.assertEqual(api.call_count, 1)

    def test_additional_pilot_is_added_to_private_team(self):
        data = {"pilot_group_id": "group", "service_principal_id": "sp", "team_id": "team"}
        responses = {
            ("GET", "/groups/group/members?$select=id"): {"value": [{"id": OWNER}, {"id": PILOT}]},
            ("PATCH", "/servicePrincipals/sp"): {},
            ("GET", "/servicePrincipals/sp/appRoleAssignedTo"): {"value": [{"principalId": "group"}]},
            ("GET", "/teams/team"): {"visibility": "private"},
            ("GET", "/teams/team/members"): {"value": [{"userId": OWNER}]},
            ("POST", "/teams/team/members"): {},
            ("GET", "/teams/team/channels"): {"value": [{"displayName": "Finance Approvals", "id": "channel"}]},
        }

        def reply(method, url, body=None):
            return responses[(method, url.removeprefix(deploy_azure.GRAPH))], {}

        with patch.dict(os.environ, {"FINANCE_PILOT_OIDS": f"{OWNER},{PILOT}",
                                     "FINANCE_APPROVER_OIDS": PILOT}, clear=True), \
                patch.object(deploy_azure, "CONFIG", self.settings()), \
                patch.object(deploy_azure, "save"), patch.object(deploy_azure, "api", side_effect=reply) as api:
            deploy_azure.provision_finance(data, OWNER)
        posts = [call for call in api.call_args_list if call.args[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertIn(PILOT, posts[0].args[2]["user@odata.bind"])
        self.assertEqual(data["finance_approver_oids"], [PILOT])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.definition = deploy_workflow.definition({
            "hostname": "waypoint.example.com", "team_id": "team", "channel_id": "channel",
            "pilot_oid": OWNER, "finance_approver_oids": [OWNER, PILOT],
        })
        self.actions = self.definition["actions"]
        self.gate = self.actions["Verify_authenticated_responder"]

    def test_only_verified_responder_reaches_decision(self):
        conditions = self.gate["expression"]["and"]
        self.assertEqual(conditions[1]["contains"][0], [OWNER, PILOT])
        self.assertIn("responder", conditions[1]["contains"][1])
        self.assertIn("check_id", conditions[2]["equals"][0])
        self.assertNotIn("Record_human_decision", self.gate["else"]["actions"])

    def test_success_notification_requires_successful_callback(self):
        notification = self.gate["actions"]["Notify_decision_recorded"]
        self.assertEqual(notification["runAfter"], {"Record_human_decision": ["Succeeded"]})
        self.assertEqual(notification["inputs"]["body"]["messageBody"],
                         "@body('Record_human_decision')?['message']")
        self.assertEqual(notification["inputs"]["body"]["recipient"], {"groupId": "team", "channelId": "channel"})
        self.assertTrue(notification["inputs"]["path"].endswith("/location/Channel"))

    def test_failure_paths_remain_failed_when_notification_fails(self):
        branches = [
            (self.gate["actions"], "Notify_decision_unconfirmed", "Hold_unconfirmed_decision",
             "Record_human_decision"),
            (self.actions, "Notify_card_unavailable", "Hold_on_card_failure_or_timeout",
             "Wait_for_Finance_response"),
        ]
        for actions, notify, hold, source in branches:
            self.assertEqual(actions[notify]["runAfter"], {source: ["Failed", "TimedOut"]})
            self.assertEqual(actions[hold]["inputs"]["runStatus"], "Failed")
            self.assertEqual(actions[hold]["runAfter"][notify], ["Succeeded", "Failed", "TimedOut"])
        otherwise = self.gate["else"]["actions"]
        self.assertEqual(otherwise["Hold_unverified_response"]["inputs"]["runStatus"], "Failed")
        self.assertIn("Failed", otherwise["Hold_unverified_response"]["runAfter"]["Notify_unverified_response"])

    def test_receipt_is_not_success_and_sensitive_actions_are_secured(self):
        self.assertEqual(self.actions["Acknowledge_intake"]["inputs"]["statusCode"], 202)
        self.assertEqual(self.actions["Reject_unconfirmed_intake"]["inputs"]["statusCode"], 503)
        self.assertEqual(self.actions["Wait_for_Finance_response"]["limit"]["timeout"], "PT1H")
        for action in [self.actions["Waypoint_check"], self.actions["Wait_for_Finance_response"],
                       self.gate["actions"]["Record_human_decision"],
                       self.gate["actions"]["Notify_decision_recorded"]]:
            self.assertEqual(action["runtimeConfiguration"]["secureData"]["properties"], ["inputs", "outputs"])
