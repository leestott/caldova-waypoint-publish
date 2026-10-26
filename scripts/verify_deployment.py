"""Exercise the live synthetic demo without pretending to make a human decision."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from deploy_azure import api, GRAPH, save, state, verify_identity
from deploy_container import get_settings


def verify(data):
    secret = get_settings(data)["flow-shared-secret"]
    host = "https://" + data["hostname"]

    def call(path, body=None, authorized=False):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + secret
        request = Request(
            host + path, data=json.dumps(body).encode() if body is not None else None,
            headers=headers, method="POST" if body is not None else "GET",
        )
        try:
            with urlopen(request, timeout=45) as response:
                content = response.read().decode()
                return response.status, json.loads(content) if content.startswith("{") else content
        except HTTPError as exc:
            return exc.code, None

    status, health = call("/health")
    assert status == 200 and health == {"status": "ready", "mode": "tenant", "backend": "synthetic"}
    print("HTTPS ready: tenant mode, synthetic backend.")
    for route in ("/", "/privacy", "/terms"):
        status, text = call(route)
        assert status == 200 and "Synthetic demonstration" in text
    for route, body in (("/api/messages", {}), ("/api/invoice-approval", {}), ("/api/telemetry", None)):
        assert call(route, body)[0] == 401, route
    print("Unsigned bot activities and unauthenticated workflow/telemetry access rejected.")
    request_id = data.get("smoke_test_request_id") or str(uuid4())
    payload = {"request_id": request_id, "invoice_id": "INV-1044", "channel_id": data["channel_id"]}
    first_status, first = call("/api/invoice-approval", payload, True)
    assert first_status == 200, first_status
    assert call("/api/invoice-approval", payload, True) == (first_status, first)
    assert "CAL-C-042 clause 4.2" in json.dumps(first) and "CAL-POL-017 section 3" in json.dumps(first)
    assert call("/api/invoice-approval", payload | {"channel_id": "not-finance"}, True)[0] == 403
    action = first["card"]["actions"][0]["data"] | {"action": "approve"}
    assert call("/api/workflow-decision", action | {"responder_oid": str(uuid4())}, True)[0] == 403
    assert call("/api/workflow-decision", action | {"responder_oid": data["pilot_oid"]}, True)[0] == 409
    print("Evidence, request idempotency, channel/approver boundaries and variance approval hold verified.")
    status, metrics = call("/api/telemetry", authorized=True)
    assert status == 200 and metrics["payment_writes"] == 0
    print("Sample usage counters (not Agent 365):", json.dumps(metrics))
    data.update(host_status="ready", smoke_test_request_id=request_id)
    save(data)
    return metrics


if __name__ == "__main__":
    verify_identity()
    verify(state())
