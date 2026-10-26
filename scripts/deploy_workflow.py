"""Deploy the synthetic invoice intake; Teams OAuth authorization remains interactive."""
import json

from deploy_azure import api, ARM, BASE, CONFIG, LOCATION, save, state, SUB, TENANT, verify_identity
from deploy_container import get_settings

WORKFLOW = BASE + "/providers/Microsoft.Logic/workflows/" + CONFIG.names["AZURE_WORKFLOW_NAME"]
CONNECTION = BASE + "/providers/Microsoft.Web/connections/" + CONFIG.names["AZURE_TEAMS_CONNECTION_NAME"]
SECURE = {"secureData": {"properties": ["inputs", "outputs"]}}


def notification(data, message, after):
    return {
        "type": "ApiConnection", "runAfter": after,
        "inputs": {
            "host": {"connection": {"name": "@parameters('$connections')['teams']['connectionId']"}},
            "method": "post",
            "path": "/beta/teams/conversation/message/poster/Flow%20bot/location/Channel",
            "body": {
                "recipient": {"groupId": data["team_id"], "channelId": data["channel_id"]},
                "messageBody": message,
            },
            "retryPolicy": {"type": "none"},
        },
        "runtimeConfiguration": SECURE,
    }


def definition(data):
    host = f"https://{data['hostname']}"
    return {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "$connections": {"type": "Object", "defaultValue": {}},
            "flowSecret": {"type": "SecureString"},
        },
        "triggers": {
            "New_invoice_approval": {
                "type": "Request", "kind": "Http",
                "inputs": {
                    "method": "POST",
                    "schema": {
                        "type": "object", "additionalProperties": False,
                        "required": ["request_id", "invoice_id"],
                        "properties": {
                            "request_id": {"type": "string", "minLength": 36, "maxLength": 36},
                            "invoice_id": {"type": "string", "enum": ["INV-1042", "INV-1043", "INV-1044"]},
                        },
                    },
                },
            },
        },
        "actions": {
            "Waypoint_check": {
                "type": "Http", "runAfter": {},
                "inputs": {
                    "method": "POST", "uri": host + "/api/invoice-approval",
                    "headers": {"Authorization": "@concat('Bearer ', parameters('flowSecret'))",
                                "Content-Type": "application/json"},
                    "body": {
                        "request_id": "@triggerBody()?['request_id']",
                        "invoice_id": "@triggerBody()?['invoice_id']", "channel_id": data["channel_id"],
                    },
                },
                "runtimeConfiguration": SECURE,
            },
            "Acknowledge_intake": {
                "type": "Response", "kind": "Http", "runAfter": {"Waypoint_check": ["Succeeded"]},
                "inputs": {"statusCode": 202, "body": {
                    "status": "accepted_pending_human_review", "payment_released": False,
                    "run_id": "@workflow().run.name",
                }},
            },
            "Reject_unconfirmed_intake": {
                "type": "Response", "kind": "Http",
                "runAfter": {"Waypoint_check": ["Failed", "TimedOut"]},
                "inputs": {"statusCode": 503, "body": {
                    "status": "check_not_confirmed",
                    "message": "Keep the invoice on hold. Inspect this run before retrying the same request ID.",
                    "run_id": "@workflow().run.name",
                }},
            },
            "Wait_for_Finance_response": {
                "type": "ApiConnectionWebhook", "runAfter": {"Acknowledge_intake": ["Succeeded"]},
                "inputs": {
                    "host": {"connection": {"name": "@parameters('$connections')['teams']['connectionId']"}},
                    "path": "/v1.0/teams/conversation/gatherinput/poster/Flow%20bot/location/Channel/$subscriptions",
                    "body": {
                        "notificationUrl": "@listCallbackUrl()",
                        "body": {
                            "recipient": {"groupId": data["team_id"], "channelId": data["channel_id"]},
                            "messageBody": "@string(body('Waypoint_check')?['card'])",
                            "updateMessage": "Response received. Waypoint must validate it before recording a decision. No payment released.",
                        },
                    },
                    "retryPolicy": {"type": "none"},
                },
                "limit": {"timeout": "PT1H"},
                "runtimeConfiguration": SECURE,
            },
            "Verify_authenticated_responder": {
                "type": "If", "runAfter": {"Wait_for_Finance_response": ["Succeeded"]},
                "expression": {"and": [
                    {"equals": [
                        "@toLower(string(body('Wait_for_Finance_response')?['responder']?['tenantId']))",
                        TENANT,
                    ]},
                    {"contains": [
                        data.get("finance_approver_oids", [data["pilot_oid"]]),
                        "@toLower(string(coalesce(body('Wait_for_Finance_response')?['responder']?['objectId'], body('Wait_for_Finance_response')?['responder']?['id'], '')))",
                    ]},
                    {"equals": [
                        "@body('Wait_for_Finance_response')?['data']?['check_id']",
                        "@triggerBody()?['request_id']",
                    ]},
                ]},
                "actions": {
                    "Record_human_decision": {
                        "type": "Http", "runAfter": {},
                        "inputs": {
                            "method": "POST", "uri": host + "/api/workflow-decision",
                            "headers": {"Authorization": "@concat('Bearer ', parameters('flowSecret'))",
                                        "Content-Type": "application/json"},
                            "body": {
                                "check_id": "@triggerBody()?['request_id']",
                                "nonce": "@body('Wait_for_Finance_response')?['data']?['nonce']",
                                "action": "@body('Wait_for_Finance_response')?['data']?['action']",
                                "responder_oid": "@toLower(string(coalesce(body('Wait_for_Finance_response')?['responder']?['objectId'], body('Wait_for_Finance_response')?['responder']?['id'], '')))",
                            },
                            "retryPolicy": {"type": "none"},
                        },
                        "runtimeConfiguration": SECURE,
                    },
                    "Notify_decision_recorded": notification(
                        data, "@body('Record_human_decision')?['message']",
                        {"Record_human_decision": ["Succeeded"]}),
                    "Notify_decision_unconfirmed": notification(
                        data,
                        "@concat('Invoice ', triggerBody()?['invoice_id'], ': decision NOT confirmed. "
                        "Keep the invoice on hold. Inspect run ', workflow().run.name, "
                        "' before retrying or requesting a fresh card. No payment released.')",
                        {"Record_human_decision": ["Failed", "TimedOut"]}),
                    "Hold_unconfirmed_decision": {
                        "type": "Terminate",
                        "runAfter": {"Notify_decision_unconfirmed": ["Succeeded", "Failed", "TimedOut"]},
                        "inputs": {"runStatus": "Failed", "runError": {
                            "code": "DecisionNotConfirmed",
                            "message": "The decision was not confirmed; inspect durable state before retrying.",
                        }},
                    },
                },
                "else": {"actions": {
                    "Notify_unverified_response": notification(
                        data,
                        "@concat('Invoice ', triggerBody()?['invoice_id'], ': responder or request "
                        "binding could not be verified. Invoice remains on hold. Ask an authorized "
                        "Finance approver to obtain a fresh card. No payment released.')", {}),
                    "Hold_unverified_response": {
                        "type": "Terminate",
                        "runAfter": {"Notify_unverified_response": ["Succeeded", "Failed", "TimedOut"]},
                        "inputs": {"runStatus": "Failed", "runError": {
                            "code": "UnverifiedFinanceResponder",
                            "message": "Identity or request binding could not be verified. Invoice remains on hold.",
                        }},
                    },
                }},
            },
            "Notify_card_unavailable": notification(
                data,
                "@concat('Invoice ', triggerBody()?['invoice_id'], ': the approval card failed or "
                "expired. Invoice remains on hold. Correct the connector issue and request a fresh "
                "card. No payment released.')",
                {"Wait_for_Finance_response": ["Failed", "TimedOut"]}),
            "Hold_on_card_failure_or_timeout": {
                "type": "Terminate",
                "runAfter": {"Notify_card_unavailable": ["Succeeded", "Failed", "TimedOut"]},
                "inputs": {"runStatus": "Failed", "runError": {
                    "code": "InvoiceHeld", "message": "Finance card failed or expired. No approval or payment executed.",
                }},
            },
        },
        "outputs": {},
    }


def deploy(data):
    connection, _ = api("GET", CONNECTION + "?api-version=2016-06-01", optional=True)
    if not connection:
        connection, _ = api("PUT", CONNECTION + "?api-version=2016-06-01", {
            "location": LOCATION, "properties": {
                "displayName": "Waypoint Finance pilot Teams",
                "api": {"id": f"/subscriptions/{SUB}/providers/Microsoft.Web/locations/{LOCATION}/managedApis/teams"},
            },
        })
    secret = get_settings(data)["flow-shared-secret"]
    api("PUT", WORKFLOW + "?api-version=2019-05-01", {
        "location": LOCATION, "tags": {"environment": "synthetic-demo"},
        "properties": {
            "state": "Enabled", "definition": definition(data),
            "parameters": {
                "flowSecret": {"value": secret},
                "$connections": {"value": {"teams": {
                    "id": f"/subscriptions/{SUB}/providers/Microsoft.Web/locations/{LOCATION}/managedApis/teams",
                    "connectionId": CONNECTION.removeprefix(ARM),
                    "connectionName": CONFIG.names["AZURE_TEAMS_CONNECTION_NAME"],
                }}},
            },
        },
    })
    data["workflow_id"] = WORKFLOW
    data["teams_connection_id"] = CONNECTION
    data["workflow_status"] = "deployed_pending_connector_authorization"
    save(data)
    print("Invoice intake workflow deployed; callback URL and flow credential have not been printed.")
    print("Teams connection status:", connection["properties"].get("statuses", []))


if __name__ == "__main__":
    verify_identity()
    deploy(state())
