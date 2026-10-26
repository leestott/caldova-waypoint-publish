"""Deploy the restricted synthetic demo. Credentials stay in memory/Azure settings."""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile
from deployment_config import DeploymentSettings, finance_oids

ROOT = Path(__file__).resolve().parent.parent
CONFIG = DeploymentSettings.load()
SUB, TENANT = CONFIG.subscription, CONFIG.tenant
RG, LOCATION = CONFIG.resource_group, CONFIG.location
WEB, BOT = CONFIG.names["AZURE_WEB_APP_NAME"], CONFIG.names["AZURE_BOT_NAME"]
ARM = "https://management.azure.com"
GRAPH = "https://graph.microsoft.com/v1.0"
BASE = f"{ARM}/subscriptions/{SUB}/resourceGroups/{RG}"
WEB_ID = f"{BASE}/providers/Microsoft.Web/sites/{WEB}"
BOT_ID = f"{BASE}/providers/Microsoft.BotService/botServices/{BOT}"
STATE = ROOT / "dist" / "deployment.json"
TOKENS = {}

class ApiError(RuntimeError):
    def __init__(self, method, url, status, details):
        self.status = status
        self.details = details
        super().__init__(
            f"{method} {url.split('?')[0]} failed ({status}); inspect the Azure/Graph error securely."
        )


def az(*args):
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Install Azure CLI and sign in to the account explicitly configured in .env.")
    result = subprocess.run(
        [executable, *args, "--only-show-errors", "--output", "json"],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Azure CLI {' '.join(args[:3])} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def token(resource):
    if resource not in TOKENS or TOKENS[resource][1] < time.time():
        value = az("account", "get-access-token", "--resource", resource, "--subscription", SUB)
        if value["tenant"] != TENANT:
            raise RuntimeError("Refusing to use a token from another tenant.")
        TOKENS[resource] = (value["accessToken"], time.time() + 1200)
    return TOKENS[resource][0]


def api(method, url, body=None, *, binary=False, optional=False):
    resource = "https://graph.microsoft.com/" if url.startswith(GRAPH) else ARM + "/"
    headers = {"Authorization": "Bearer " + token(resource)}
    payload = body if binary else (json.dumps(body).encode() if body is not None else None)
    if payload is not None:
        headers["Content-Type"] = "application/zip" if binary else "application/json"
    try:
        with urlopen(Request(url, data=payload, headers=headers, method=method), timeout=180) as response:
            raw = response.read()
            return (json.loads(raw) if raw else None), dict(response.headers)
    except HTTPError as exc:
        if optional and exc.code == 404:
            return None, {}
        error = json.loads(exc.read() or b"{}")
        raise ApiError(method, url, exc.code, error.get("error", error)) from None


def state():
    current = CONFIG.identity()
    data = json.loads(STATE.read_text()) if STATE.exists() else current.copy()
    for key, value in current.items():
        if data.get(key) != value:
            raise RuntimeError("Deployment state belongs to a different target. Preserve it and use a fresh checkout.")
    if data.get("resource_names", CONFIG.names) != CONFIG.names:
        raise RuntimeError("Resource names changed since deployment. Use a fresh checkout for a new deployment.")
    return data


def save(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(STATE.with_suffix(".lock.sqlite3"), timeout=30)) as lock, lock:
        lock.execute("BEGIN EXCLUSIVE")
        merged = state() | data | {"resource_names": CONFIG.names}
        temporary = STATE.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(json.dumps(merged, indent=2))
        os.replace(temporary, STATE)
        data.update(merged)


def verify_identity():
    CONFIG.validate()
    state()
    account = az("account", "show", "--subscription", SUB)
    if (account["tenantId"] != TENANT
            or account["user"]["name"].lower() != CONFIG.operator):
        raise RuntimeError("Azure CLI account does not match TENANT_ID and DEPLOYMENT_USER_PRINCIPAL_NAME in .env.")
    user, _ = api("GET", GRAPH + "/me?$select=id")
    return user["id"]


def provision_identity(data, user_id):
    display_name = CONFIG.names["APP_REGISTRATION_NAME"]
    apps, _ = api("GET", GRAPH + "/applications?" + urlencode({
        "$filter": "displayName eq '" + display_name.replace("'", "''") + "'",
        "$select": "id,appId,api",
    }))
    if len(apps["value"]) > 1:
        raise RuntimeError("Duplicate app registrations; refusing to choose an identity.")
    if apps["value"]:
        app = apps["value"][0]
        if data.get("app_object_id") != app["id"]:
            raise RuntimeError("An untracked app already uses this name. Choose a unique APP_REGISTRATION_NAME.")
    else:
        app, _ = api("POST", GRAPH + "/applications", {
            "displayName": display_name, "signInAudience": "AzureADMyOrg",
            "web": {"redirectUris": ["https://token.botframework.com/.auth/web/redirect"]},
            "requiredResourceAccess": [{
                "resourceAppId": "00000003-0000-0000-c000-000000000000",
                "resourceAccess": [{"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"}],
            }],
        })
    data.update(bot_client_id=app["appId"], app_object_id=app["id"],
                package_id=data.get("package_id", str(uuid4())), pilot_oid=user_id)
    save(data)
    scope_id = next((scope["id"] for scope in app.get("api", {}).get("oauth2PermissionScopes", [])
                     if scope["value"] == "defaultScopes"), str(uuid4()))
    trusted_clients = [
        "1fec8e78-bce4-4aaf-ab1b-5451cc387264", "5e3ce6c0-2b1f-4285-8d4b-75ee78787346",
        "4765445b-32c6-49b0-83e6-1d93765276ca", "0ec893e0-5785-4de6-99da-4ed124e5296c",
    ]
    api("PATCH", GRAPH + f"/applications/{app['id']}", {
        "identifierUris": [f"api://botid-{app['appId']}"],
        "api": {
            "requestedAccessTokenVersion": 2,
            "oauth2PermissionScopes": [{
                "id": scope_id, "value": "defaultScopes", "type": "Admin", "isEnabled": True,
                "adminConsentDisplayName": "Use the Waypoint synthetic demo",
                "adminConsentDescription": "Allow approved Finance pilot users to sign in to the synthetic demo.",
            }],
        },
    })
    api("PATCH", GRAPH + f"/applications/{app['id']}", {
        "api": {"preAuthorizedApplications": [
            {"appId": client, "delegatedPermissionIds": [scope_id]} for client in trusted_clients
        ]},
    })
    principals, _ = api("GET", GRAPH + "/servicePrincipals?" + urlencode({
        "$filter": f"appId eq '{app['appId']}'", "$select": "id",
    }))
    sp = principals["value"][0] if principals["value"] else api(
        "POST", GRAPH + "/servicePrincipals", {"appId": app["appId"]}
    )[0]
    data["service_principal_id"] = sp["id"]
    save(data)
    print("Single-tenant bot identity and Teams/Microsoft 365 SSO scope configured.")


def provision_finance(data, user_id):
    pilots, approvers = finance_oids(user_id)
    data.update(finance_pilot_oids=pilots, finance_approver_oids=approvers)
    group_name = CONFIG.names["FINANCE_PILOT_GROUP_NAME"]
    team_name = CONFIG.names["FINANCE_TEAM_NAME"]
    channel_name = CONFIG.names["FINANCE_CHANNEL_NAME"]
    if not data.get("pilot_group_id"):
        groups, _ = api("GET", GRAPH + "/groups?" + urlencode({
            "$filter": "displayName eq '" + group_name.replace("'", "''") + "'", "$select": "id",
        }))
        if len(groups["value"]) > 1:
            raise RuntimeError("Duplicate Finance pilot groups; select one explicitly.")
        group = groups["value"][0] if groups["value"] else api("POST", GRAPH + "/groups", {
            "displayName": group_name, "mailEnabled": False,
            "mailNickname": CONFIG.prefix.replace("-", "") + "financepilot", "securityEnabled": True,
            "description": "Restricted synthetic Caldova demonstration pilot.",
            "owners@odata.bind": [GRAPH + f"/users/{user_id}"],
            "members@odata.bind": [GRAPH + f"/users/{oid}" for oid in pilots],
        })[0]
        data["pilot_group_id"] = group["id"]
        save(data)
    members, _ = api("GET", GRAPH + f"/groups/{data['pilot_group_id']}/members?$select=id")
    if members.get("@odata.nextLink"):
        raise RuntimeError("This small demo does not manage paginated pilot groups; use a dedicated small group.")
    actual = {member["id"].lower() for member in members["value"]}
    if actual - set(pilots):
        raise RuntimeError("Existing pilot membership is broader than .env. Reconcile it explicitly before deployment.")
    for oid in set(pilots) - actual:
        api("POST", GRAPH + f"/groups/{data['pilot_group_id']}/members/$ref",
            {"@odata.id": GRAPH + f"/directoryObjects/{oid}"})
    api("PATCH", GRAPH + f"/servicePrincipals/{data['service_principal_id']}",
        {"appRoleAssignmentRequired": True})
    assignments, _ = api("GET", GRAPH + f"/servicePrincipals/{data['service_principal_id']}/appRoleAssignedTo")
    if not any(item["principalId"] == data["pilot_group_id"] for item in assignments["value"]):
        api("POST", GRAPH + f"/servicePrincipals/{data['service_principal_id']}/appRoleAssignedTo", {
            "principalId": data["pilot_group_id"], "resourceId": data["service_principal_id"],
            "appRoleId": "00000000-0000-0000-0000-000000000000",
        })
    if not data.get("team_id") and not data.get("team_operation"):
        teams, _ = api("GET", GRAPH + "/me/joinedTeams?$select=id,displayName")
        matching = [item for item in teams["value"] if item["displayName"] == team_name]
        if len(matching) > 1:
            raise RuntimeError("Duplicate Finance teams; refusing to choose a destination.")
        if matching:
            data["team_id"] = matching[0]["id"]
        else:
            _, headers = api("POST", GRAPH + "/teams", {
                "template@odata.bind": GRAPH + "/teamsTemplates('standard')",
                "displayName": team_name,
                "description": "Private synthetic invoice-approval demonstration. No payment execution.",
                "visibility": "private", "firstChannelName": channel_name,
                "members": [{
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"], "user@odata.bind": GRAPH + f"/users('{user_id}')",
                }],
            })
            location = next((value for key, value in headers.items() if key.lower() == "location"), None)
            if not location:
                raise RuntimeError("Teams creation accepted without an operation URL; inspect tenant before retrying.")
            data["team_operation"] = location if location.startswith("https://") else GRAPH + location.removeprefix("/v1.0")
        save(data)
    if not data.get("team_id"):
        for _ in range(60):
            operation, _ = api("GET", data["team_operation"])
            if operation["status"] == "succeeded":
                data["team_id"] = operation["targetResourceId"]
                save(data)
                break
            if operation["status"] == "failed":
                raise RuntimeError(f"Teams provisioning failed: {operation.get('error')}")
            time.sleep(10)
        else:
            raise RuntimeError("Teams provisioning still pending; operation saved, do not create another team.")
    team, _ = api("GET", GRAPH + f"/teams/{data['team_id']}")
    if team.get("visibility") != "private":
        raise RuntimeError("Finance destination must be a private Team.")
    members, _ = api("GET", GRAPH + f"/teams/{data['team_id']}/members")
    if members.get("@odata.nextLink"):
        raise RuntimeError("Use a dedicated small Finance Team; paginated membership is not managed.")
    expected = set(pilots) | {user_id.lower()}
    actual = {member.get("userId", "").lower() for member in members["value"]}
    if actual - expected:
        raise RuntimeError("Finance Team membership exceeds the configured pilot plus owner. Reconcile it explicitly.")
    for oid in expected - actual:
        api("POST", GRAPH + f"/teams/{data['team_id']}/members", {
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "roles": [], "user@odata.bind": GRAPH + f"/users('{oid}')",
        })
    channels, _ = api("GET", GRAPH + f"/teams/{data['team_id']}/channels")
    finance = [item for item in channels["value"] if item["displayName"] == channel_name]
    if not finance:
        raise RuntimeError("Finance Approvals channel not yet available.")
    data.update(channel_id=finance[0]["id"], channel_url=finance[0].get("webUrl"))
    save(data)
    print("Restricted pilot group, application assignment and private Finance team/channel configured.")


def provision_host(data):
    if not WEB or not CONFIG.names["AZURE_APP_SERVICE_PLAN"]:
        raise ValueError("The optional App Service host requires AZURE_WEB_APP_NAME and AZURE_APP_SERVICE_PLAN.")
    plan_id = f"{BASE}/providers/Microsoft.Web/serverfarms/{CONFIG.names['AZURE_APP_SERVICE_PLAN']}"
    api("PUT", plan_id + "?api-version=2023-12-01", {
        "location": LOCATION, "kind": "linux",
        "sku": {"name": "B1", "tier": "Basic", "capacity": 1},
        "properties": {"reserved": True},
        "tags": {"project": CONFIG.prefix, "environment": "synthetic-demo"},
    })
    site, _ = api("PUT", WEB_ID + "?api-version=2023-12-01", {
        "location": LOCATION, "kind": "app,linux", "identity": {"type": "SystemAssigned"},
        "tags": {"project": CONFIG.prefix, "environment": "synthetic-demo"},
        "properties": {
            "serverFarmId": plan_id.removeprefix(ARM), "httpsOnly": True,
            "siteConfig": {
                "linuxFxVersion": "PYTHON|3.13", "alwaysOn": True,
                "appCommandLine": "python -m waypoint.server",
                "minTlsVersion": "1.2", "ftpsState": "Disabled", "http20Enabled": True,
                "healthCheckPath": "/health",
            },
        },
    })
    data.update(webapp_name=WEB, webapp_id=WEB_ID,
                hostname=site["properties"]["defaultHostName"])
    save(data)
    current, _ = api("POST", WEB_ID + "/config/appsettings/list?api-version=2023-12-01")
    settings = current.get("properties", {})
    if not settings.get("CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"):
        credential, _ = api("POST", GRAPH + f"/applications/{data['app_object_id']}/addPassword", {
            "passwordCredential": {
                "displayName": "Waypoint Ignite demo host",
                "endDateTime": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            },
        })
        settings["CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET"] = credential["secretText"]
        data["host_credential_expires"] = credential["endDateTime"]
        save(data)
    settings.update({
        "WAYPOINT_MODE": "tenant", "TENANT_ID": TENANT,
        "HOST": "0.0.0.0", "PORT": "8000",
        "WAYPOINT_DATABASE": "/home/waypoint/waypoint.sqlite3",
        "FINANCE_PILOT_OIDS": ",".join(finance_oids(data["pilot_oid"])[0]),
        "FINANCE_APPROVER_OIDS": ",".join(finance_oids(data["pilot_oid"])[1]),
        "FINANCE_CHANNEL_ID": data["channel_id"],
        "FLOW_SHARED_SECRET": settings.get("FLOW_SHARED_SECRET") or secrets.token_urlsafe(48),
        "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID": data["bot_client_id"],
        "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID": TENANT,
        "CONNECTIONSMAP__0__SERVICEURL": "*",
        "CONNECTIONSMAP__0__CONNECTION": "SERVICE_CONNECTION",
        "AGENTAPPLICATION__USERAUTHORIZATION__HANDLERS__GRAPH__SETTINGS__AZUREBOTOAUTHCONNECTIONNAME": CONFIG.names["BOT_OAUTH_CONNECTION_NAME"],
        "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
        "ENABLE_ORYX_BUILD": "true", "WEBSITES_ENABLE_APP_SERVICE_STORAGE": "true",
    })
    api("PUT", WEB_ID + "/config/appsettings?api-version=2023-12-01", {"properties": settings})
    for policy in ("ftp", "scm"):
        api("PUT", WEB_ID + f"/basicPublishingCredentialsPolicies/{policy}?api-version=2023-12-01",
            {"properties": {"allow": False}})
    print("Basic B1 Linux hosting configured; persistent state and secrets held in Azure, not source files.")


def provision_bot(data):
    bot, _ = api("PUT", BOT_ID + "?api-version=2022-09-15", {
        "location": "global", "kind": "azurebot", "sku": {"name": "F0"},
        "properties": {
            "displayName": "Waypoint", "description": "Restricted synthetic Caldova invoice assurance demo.",
            "endpoint": f"https://{data['hostname']}/api/messages",
            "msaAppId": data["bot_client_id"], "msaAppType": "SingleTenant", "msaAppTenantId": TENANT,
        },
    })
    api("PUT", BOT_ID + "/channels/MsTeamsChannel?api-version=2022-09-15", {
        "location": "global", "properties": {
            "channelName": "MsTeamsChannel", "properties": {"isEnabled": True},
        },
    })
    unique = CONFIG.names["BOT_TOKEN_STORE_NAME"]
    tenant_encoded = base64.urlsafe_b64encode(__import__("uuid").UUID(TENANT).bytes_le).decode().rstrip("=")
    subject = f"/eid1/c/pub/t/{tenant_encoded}/a/9ExAW52n_ky4ZiS_jhpJIQ/{unique}"
    credentials, _ = api("GET", GRAPH + f"/applications/{data['app_object_id']}/federatedIdentityCredentials")
    if not any(item["name"] == unique for item in credentials["value"]):
        api("POST", GRAPH + f"/applications/{data['app_object_id']}/federatedIdentityCredentials", {
            "name": unique, "issuer": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "subject": subject, "audiences": ["api://AzureADTokenExchange"],
        })
    api("PUT", BOT_ID + f"/connections/{CONFIG.names['BOT_OAUTH_CONNECTION_NAME']}?api-version=2022-09-15", {
        "location": "global", "properties": {
            "clientId": data["bot_client_id"], "scopes": "openid profile offline_access User.Read",
            "serviceProviderId": "c00b44ab-5e16-c44c-af26-2fd5bc55eb18",
            "parameters": [
                {"key": "TenantId", "value": TENANT},
                {"key": "TokenExchangeUrl", "value": f"api://botid-{data['bot_client_id']}"},
                {"key": "UniqueIdentifier", "value": unique},
                {"key": "LoginUri", "value": "https://login.microsoftonline.com"},
                {"key": "IsMultiTenantFlowSupported", "value": "false"},
            ],
        },
    })
    data["bot_resource_id"] = BOT_ID
    save(data)
    print("Azure Bot F0, Teams channel and federated single-tenant OAuth connection configured.")


def deploy_code(data):
    archive = ROOT / "dist" / "waypoint-host.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as package:
        for folder in ("waypoint", "data"):
            for file in (ROOT / folder).rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    package.write(file, file.relative_to(ROOT).as_posix())
        package.write(ROOT / "requirements.txt", "requirements.txt")
    print("Deploying application source with remote dependency build.")
    result = az("webapp", "deploy", "--subscription", SUB, "--resource-group", RG,
                "--name", WEB, "--src-path", str(archive), "--type", "zip",
                "--timeout", "900000")
    print("Azure App Service deployment command completed.")
    for _ in range(60):
        try:
            with urlopen(f"https://{data['hostname']}/health", timeout=20) as response:
                health = json.load(response)
            if health.get("mode") == "tenant" and health.get("status") == "ready":
                data["host_status"] = "ready"
                save(data)
                print("Live HTTPS health verified: tenant mode, synthetic backend.")
                return
        except (HTTPError, TimeoutError, OSError) as exc:
            print(f"Waiting for host readiness ({type(exc).__name__}).")
        time.sleep(10)
    raise RuntimeError("Application deployment returned, but HTTPS readiness was not confirmed.")


def package_app(data, compatibility=False):
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.package import build
    os.environ.update({
        "APP_ID": data["package_id"], "BOT_ID": data["bot_client_id"],
        "BOT_DOMAIN": data["hostname"], "APP_BASE_URL": f"https://{data['hostname']}",
    })
    package = build(False, compatibility)
    data["manifest_version"] = "1.24" if compatibility else "1.30"
    save(data)
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("bootstrap", "identity", "finance", "host", "bot", "code", "package"))
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    data = state()
    user = verify_identity()
    if args.phase == "bootstrap":
        az("group", "create", "--subscription", SUB, "--name", RG, "--location", LOCATION)
        for provider in ("Microsoft.App", "Microsoft.ContainerRegistry", "Microsoft.ManagedIdentity",
                         "Microsoft.Storage", "Microsoft.Web", "Microsoft.Logic", "Microsoft.BotService"):
            az("provider", "register", "--subscription", SUB, "--namespace", provider, "--wait")
        print("Dedicated resource group and required Azure providers are ready.")
    elif args.phase == "identity":
        provision_identity(data, user)
    elif args.phase == "finance":
        provision_finance(data, user)
    elif args.phase == "host":
        provision_host(data)
    elif args.phase == "bot":
        provision_bot(data)
    elif args.phase == "code":
        deploy_code(data)
    else:
        package_app(data, args.compatibility)
