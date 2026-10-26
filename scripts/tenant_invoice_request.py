"""Start a new synthetic approval request without exposing the workflow SAS URL."""
import argparse
import json
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from deploy_azure import api, BASE, save, state, verify_identity
from deploy_workflow import CONNECTION, WORKFLOW


def request_invoice(invoice, request_id):
    verify_identity()
    data = state()
    connection, _ = api("GET", CONNECTION + "?api-version=2016-06-01")
    if not any(item.get("status") == "Connected" for item in connection["properties"].get("statuses", [])):
        raise RuntimeError("Teams connector is not authenticated. No invoice was triggered; resolve consent first.")
    callback, _ = api("POST", WORKFLOW + "/triggers/New_invoice_approval/listCallbackUrl?api-version=2016-06-01")
    payload = {"invoice_id": invoice, "request_id": str(UUID(request_id))}
    with urlopen(Request(callback["value"], data=json.dumps(payload).encode(),
                         headers={"Content-Type": "application/json"}, method="POST"), timeout=90) as response:
        result = json.load(response)
    data.update(last_workflow_request_id=request_id, last_workflow_invoice_id=invoice,
                last_workflow_run_id=result["run_id"])
    save(data)
    print("Synthetic approval intake accepted; no payment released.")
    print("Request ID (reuse this on retries):", request_id)
    print("Logic App run ID:", result["run_id"])
    print("Open the Finance Approvals channel and inspect the run before claiming the card was posted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--invoice", choices=("INV-1042", "INV-1043", "INV-1044"), default="INV-1044")
    parser.add_argument("--request-id", default=str(uuid4()))
    args = parser.parse_args()
    request_invoice(args.invoice, args.request_id)
