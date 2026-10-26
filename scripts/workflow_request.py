"""Send a synthetic approval signal to the running local server."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
if os.getenv("WAYPOINT_MODE", "local") != "local":
    raise SystemExit("This loopback request helper is for local mode only; use the tenant flow for live posting.")
payload = {
    "invoice_id": "INV-1044",
    "request_id": str(uuid4()),
    "channel_id": "local-finance",
}
request = Request(
    f"http://127.0.0.1:{os.getenv('PORT', '3978')}/api/invoice-approval",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json",
             "Authorization": f"Bearer {os.environ['FLOW_SHARED_SECRET']}"},
)
try:
    with urlopen(request, timeout=10) as response:
        result = json.load(response)
except HTTPError as exc:
    raise SystemExit(f"Workflow failed ({exc.code}): {exc.read().decode()}") from exc
output = ROOT / "dist" / "workflow-response.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result, indent=2))
print(f"Synthetic approval checked. Card saved to {output}; no Teams message was posted.")
