"""Repeatable offline run; output is explicitly not Teams or an admin portal."""
import json
from pathlib import Path
from uuid import uuid4

from .core import Principal, ROOT, Waypoint


def main():
    engine = Waypoint()
    babak = Principal("local-babak", True, True)
    output = ROOT / "dist" / "cards"
    output.mkdir(parents=True, exist_ok=True)
    card = engine.check("INV-1042", babak, "chat")
    (output / "babak-anomaly.json").write_text(json.dumps(card, indent=2))
    action = card["actions"][0]["data"]
    print("LOCAL SYNTHETIC REHEARSAL - no Microsoft 365 connection")
    print("Babak Shammas: Check invoice INV-1042 against contract")
    print("Billed GBP 12,500; contract GBP 10,000; variance GBP 2,500.")
    print(engine.decide(action["check_id"], action["nonce"], "escalate", babak))
    workflow = engine.check("INV-1044", Principal("workflow", True, False), "workflow", str(uuid4()))
    (output / "workflow-channel-card.json").write_text(json.dumps(workflow, indent=2))
    clean = engine.check("INV-1043", babak, "chat")
    approve = clean["actions"][0]["data"]
    print(engine.decide(approve["check_id"], approve["nonce"], "approve", babak))
    print("Workflow card prepared for the Finance channel; not posted in local mode.")
    print(json.dumps(engine.metrics(), indent=2))
    print(f"Adaptive Card JSON: {output}")


if __name__ == "__main__":
    main()
