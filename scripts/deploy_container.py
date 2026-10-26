"""Azure Container Apps alternative for subscriptions with zero App Service quota."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from deploy_azure import (
    api, ARM, az, BASE, CONFIG, GRAPH, LOCATION, ROOT, save, state, SUB, TENANT, verify_identity,
    finance_oids,
)

REGISTRY = CONFIG.names["AZURE_CONTAINER_REGISTRY"]
STORAGE = CONFIG.names["AZURE_STORAGE_ACCOUNT"]
ENVIRONMENT = CONFIG.names["AZURE_CONTAINER_ENVIRONMENT"]
APP = CONFIG.names["AZURE_CONTAINER_APP_NAME"]
REGISTRY_ID = BASE + "/providers/Microsoft.ContainerRegistry/registries/" + REGISTRY
STORAGE_ID = BASE + "/providers/Microsoft.Storage/storageAccounts/" + STORAGE
ENVIRONMENT_ID = BASE + "/providers/Microsoft.App/managedEnvironments/" + ENVIRONMENT
APP_RESOURCE = BASE + "/providers/Microsoft.App/containerApps/" + APP
IDENTITY_ID = BASE + "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/" + CONFIG.names["AZURE_MANAGED_IDENTITY_NAME"]
VERSION = "2025-01-01"


def wait_resource(url):
    for _ in range(90):
        result, _ = api("GET", url)
        status = result.get("properties", {}).get("provisioningState")
        if status in (None, "Succeeded"):
            return result
        if status in ("Failed", "Canceled"):
            raise RuntimeError(f"Azure provisioning failed for {result.get('name')}: {status}")
        time.sleep(10)
    raise RuntimeError(f"Provisioning still pending for {url.split('?')[0]}; inspect before retrying.")


def get_settings(data):
    """Return secrets only in memory, never write them to deployment.json."""
    result, _ = api("POST", APP_RESOURCE + f"/listSecrets?api-version={VERSION}")
    return {item["name"]: item.get("value", "") for item in result.get("value", [])}


def infrastructure(data):
    url = REGISTRY_ID + "?api-version=2023-07-01"
    existing, _ = api("GET", url, optional=True)
    if not existing:
        api("PUT", url, {
            "location": LOCATION, "sku": {"name": "Basic"},
            "properties": {"adminUserEnabled": False, "anonymousPullEnabled": False},
            "tags": {"environment": "synthetic-demo"},
        })
    registry = wait_resource(url)
    data.update(registry_name=REGISTRY, registry_server=registry["properties"]["loginServer"])
    save(data)
    identity, _ = api("GET", IDENTITY_ID + "?api-version=2023-01-31", optional=True)
    if not identity:
        identity, _ = api("PUT", IDENTITY_ID + "?api-version=2023-01-31", {"location": LOCATION})
    assignment = data.get("registry_pull_assignment") or str(uuid4())
    data["registry_pull_assignment"] = assignment
    save(data)
    api("PUT", REGISTRY_ID + "/providers/Microsoft.Authorization/roleAssignments/" + assignment
        + "?api-version=2022-04-01", {
            "properties": {
                "principalId": identity["properties"]["principalId"],
                "principalType": "ServicePrincipal",
                "roleDefinitionId": f"/subscriptions/{SUB}/providers/Microsoft.Authorization/"
                                    "roleDefinitions/7f951dda-4ed3-4680-a7ca-43fe172d538d",
            },
        })
    url = STORAGE_ID + "?api-version=2023-05-01"
    existing, _ = api("GET", url, optional=True)
    if not existing:
        api("PUT", url, {
            "location": LOCATION, "kind": "StorageV2", "sku": {"name": "Standard_LRS"},
            "properties": {
                "minimumTlsVersion": "TLS1_2", "allowBlobPublicAccess": False,
                "supportsHttpsTrafficOnly": True, "accessTier": "Hot",
            },
            "tags": {"environment": "synthetic-demo"},
        })
    wait_resource(url)
    container_id = STORAGE_ID + "/blobServices/default/containers/waypoint-state"
    api("PUT", container_id + "?api-version=2023-05-01", {"properties": {"publicAccess": "None"}})
    assignment = data.get("state_blob_assignment") or str(uuid4())
    data["state_blob_assignment"] = assignment
    save(data)
    api("PUT", container_id + "/providers/Microsoft.Authorization/roleAssignments/" + assignment
        + "?api-version=2022-04-01", {
            "properties": {
                "principalId": identity["properties"]["principalId"],
                "principalType": "ServicePrincipal",
                "roleDefinitionId": f"/subscriptions/{SUB}/providers/Microsoft.Authorization/"
                                    "roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe",
            },
        })
    url = ENVIRONMENT_ID + f"?api-version={VERSION}"
    existing, _ = api("GET", url, optional=True)
    if not existing:
        api("PUT", url, {
            "location": LOCATION,
            "properties": {
                "workloadProfiles": [{"name": "Consumption", "workloadProfileType": "Consumption"}],
            },
        })
    wait_resource(url)
    data["state_blob_url"] = f"https://{STORAGE}.blob.core.windows.net/waypoint-state/waypoint.sqlite3"
    data.update(container_environment_id=ENVIRONMENT_ID, containerapp_id=APP_RESOURCE,
                storage_account=STORAGE, hosting="Azure Container Apps")
    save(data)
    print("Container environment, private registry, managed identity and restricted Blob state container ready.")


def build_image(data):
    from check_public import check_files, source_files
    files = source_files(ROOT)
    check_files(files, ROOT)
    tag = "waypoint:" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    print("Building the sanitized image in Azure Container Registry.")
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is required for the remote image build.")
    (ROOT / "dist").mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="container-source-", dir=ROOT / "dist") as directory:
        staging = Path(directory)
        for name, content in files.items():
            if name.startswith(("waypoint/", "data/")) or name in {"Dockerfile", "requirements.txt"}:
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        result = subprocess.run([
            executable, "acr", "build", "--subscription", SUB, "--registry", REGISTRY,
            "--image", tag, "--file", "Dockerfile", "--no-logs", "--only-show-errors", str(staging),
        ], capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("Azure image build failed: " + result.stderr.strip())
    data["container_image"] = data["registry_server"] + "/" + tag
    save(data)
    print("Container image built successfully.")


def configure_app(data):
    existing, _ = api("GET", APP_RESOURCE + f"?api-version={VERSION}", optional=True)
    stored = get_settings(data) if existing else {}
    client_secret = stored.get("bot-client-secret")
    if not client_secret:
        credential, _ = api("POST", GRAPH + f"/applications/{data['app_object_id']}/addPassword", {
            "passwordCredential": {
                "displayName": "Waypoint Ignite Container Apps host",
                "endDateTime": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            },
        })
        client_secret = credential["secretText"]
        data["host_credential_expires"] = credential["endDateTime"]
        data["host_credential_key_id"] = credential["keyId"]
        save(data)
    flow_secret = stored.get("flow-shared-secret") or secrets.token_urlsafe(48)
    settings = {
        "WAYPOINT_MODE": "tenant", "TENANT_ID": TENANT, "HOST": "0.0.0.0", "PORT": "8000",
        "WAYPOINT_DATABASE": "/tmp/waypoint/waypoint.sqlite3",
        "WAYPOINT_STATE_BLOB_URL": data["state_blob_url"],
        "FINANCE_PILOT_OIDS": ",".join(finance_oids(data["pilot_oid"])[0]),
        "FINANCE_APPROVER_OIDS": ",".join(finance_oids(data["pilot_oid"])[1]),
        "FINANCE_CHANNEL_ID": data["channel_id"],
        "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID": data["bot_client_id"],
        "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID": TENANT,
        "CONNECTIONSMAP__0__SERVICEURL": "*",
        "CONNECTIONSMAP__0__CONNECTION": "SERVICE_CONNECTION",
        "AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH__SETTINGS__AZUREBOTOAUTHCONNECTIONNAME": CONFIG.names["BOT_OAUTH_CONNECTION_NAME"],
    }
    identity, _ = api("GET", IDENTITY_ID + "?api-version=2023-01-31")
    settings["AZURE_CLIENT_ID"] = identity["properties"]["clientId"]
    env = [{"name": name, "value": value} for name, value in settings.items()]
    env += [
        {"name": "FLOW_SHARED_SECRET", "secretRef": "flow-shared-secret"},
        {"name": "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET", "secretRef": "bot-client-secret"},
    ]
    api("PUT", APP_RESOURCE + f"?api-version={VERSION}", {
        "location": LOCATION,
        "identity": {"type": "UserAssigned", "userAssignedIdentities": {IDENTITY_ID.removeprefix(ARM): {}}},
        "properties": {
            "managedEnvironmentId": ENVIRONMENT_ID.removeprefix(ARM), "workloadProfileName": "Consumption",
            "configuration": {
                "activeRevisionsMode": "Single",
                "ingress": {"external": True, "targetPort": 8000, "transport": "auto",
                            "allowInsecure": False},
                "registries": [{"server": data["registry_server"], "identity": IDENTITY_ID.removeprefix(ARM)}],
                "secrets": [
                    {"name": "flow-shared-secret", "value": flow_secret},
                    {"name": "bot-client-secret", "value": client_secret},
                ],
            },
            "template": {
                "containers": [{
                    "name": "waypoint", "image": data["container_image"],
                    "resources": {"cpu": 0.5, "memory": "1Gi"}, "env": env,
                    "probes": [
                        {"type": kind, "httpGet": {"path": "/health", "port": 8000},
                         "initialDelaySeconds": 15, "periodSeconds": 10,
                         "failureThreshold": 30 if kind == "Startup" else 3}
                        for kind in ("Startup", "Liveness", "Readiness")
                    ],
                }],
                "scale": {"minReplicas": 1, "maxReplicas": 1},
                "volumes": [],
            },
        },
    })
    app = wait_resource(APP_RESOURCE + f"?api-version={VERSION}")
    data["hostname"] = app["properties"]["configuration"]["ingress"]["fqdn"]
    save(data)
    print("Container App provisioned with HTTPS, one replica and persistent synthetic-demo state.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("infrastructure", "build", "configure"))
    args = parser.parse_args()
    verify_identity()
    data = state()
    {"infrastructure": infrastructure, "build": build_image, "configure": configure_app}[args.phase](data)
