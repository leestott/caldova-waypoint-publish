"""Submit, never approve, the package using a separate delegated publisher sign-in."""
import json
import time

import msal

from deploy_azure import ApiError, api, GRAPH, ROOT, save, state, TENANT, TOKENS, urlencode, verify_identity


def submit():
    verify_identity()
    data = state()
    if data.get("catalog_app_id"):
        raise RuntimeError("A submission is already recorded. Inspect it in the admin center before resubmitting.")
    graph, _ = api("GET", GRAPH + "/servicePrincipals?" + urlencode({
        "$filter": "appId eq '00000003-0000-0000-c000-000000000000'",
        "$select": "id,oauth2PermissionScopes",
    }))
    scopes = {item["value"]: item["id"] for item in graph["value"][0]["oauth2PermissionScopes"]}
    if not data.get("publisher_app_object_id"):
        app, _ = api("POST", GRAPH + "/applications", {
            "displayName": "Waypoint Ignite package submission",
            "signInAudience": "AzureADMyOrg", "isFallbackPublicClient": True,
            "publicClient": {"redirectUris": ["http://localhost"]},
            "requiredResourceAccess": [{
                "resourceAppId": "00000003-0000-0000-c000-000000000000",
                "resourceAccess": [{"id": scopes[name], "type": "Scope"}
                                   for name in ("AppCatalog.Submit", "User.Read")],
            }],
        })
        data.update(publisher_app_object_id=app["id"], publisher_client_id=app["appId"])
        save(data)
        api("POST", GRAPH + "/servicePrincipals", {"appId": app["appId"]})
    client = msal.PublicClientApplication(
        data["publisher_client_id"], authority=f"https://login.microsoftonline.com/{TENANT}"
    )
    flow = client.initiate_device_flow(scopes=[
        "https://graph.microsoft.com/AppCatalog.Submit", "https://graph.microsoft.com/User.Read",
    ])
    if "user_code" not in flow:
        raise RuntimeError("Microsoft did not start device sign-in: " + flow.get("error_description", "unknown error"))
    print(flow["message"], flush=True)
    result = client.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError("Package publisher sign-in failed: " + result.get("error_description", "unknown error"))
    TOKENS["https://graph.microsoft.com/"] = (result["access_token"], time.time() + 300)
    user, _ = api("GET", GRAPH + "/me?$select=id")
    if user["id"] != data["pilot_oid"]:
        raise RuntimeError("Publisher sign-in used an unexpected account; no package submitted.")
    package = ROOT / "dist" / "tenant" / "waypoint.zip"
    original = package.read_bytes()
    try:
        app, _ = api("POST", GRAPH + "/appCatalogs/teamsApps?requiresReview=true", original, binary=True)
    except ApiError as exc:
        if exc.status != 400:
            raise
        print(str(exc), flush=True)
        data["catalog_submission"] = "rejected_manifest_parse"
        data["catalog_error"] = exc.details
        save(data)
        print("Submission rejected. Waiting up to fifteen minutes for a corrected package; no app was approved.", flush=True)
        for _ in range(180):
            time.sleep(5)
            corrected = package.read_bytes()
            if corrected != original:
                app, _ = api("POST", GRAPH + "/appCatalogs/teamsApps?requiresReview=true",
                             corrected, binary=True)
                break
        else:
            raise RuntimeError("Submission remains rejected; no corrected package was provided.") from exc
    data.update(catalog_app_id=app["id"], catalog_submission="submitted_for_review")
    save(data)
    print("Package submitted for admin review; no approval, organization-wide publication or installation performed.")
    print("Catalog app ID:", app["id"])
    TOKENS.pop("https://graph.microsoft.com/", None)
    api("DELETE", GRAPH + f"/applications/{data['publisher_app_object_id']}")
    data["publisher_status"] = "temporary_publisher_deleted_after_submission"
    save(data)
    print("Temporary publisher registration removed; its token was never written to disk.")


if __name__ == "__main__":
    submit()
