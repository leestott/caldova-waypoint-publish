from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent


class DemoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Principal:
    oid: str
    can_read: bool
    can_decide: bool


class Waypoint:
    """Deterministic orchestrator/evidence/write-boundary stand-in."""

    def __init__(self, database: Path | None = None):
        self.database = database or Path(os.getenv(
            "WAYPOINT_DATABASE", str(ROOT / "state" / "waypoint.sqlite3")
        ))
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.blob_state = None
        if os.getenv("WAYPOINT_STATE_BLOB_URL"):
            from .state import BlobState
            self.blob_state = BlobState(os.environ["WAYPOINT_STATE_BLOB_URL"])
        self.seed = json.loads((ROOT / "data" / "seed.json").read_text())
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS checks (
                    id TEXT PRIMARY KEY, invoice TEXT NOT NULL,
                    source TEXT NOT NULL, nonce TEXT NOT NULL,
                    created_at TEXT NOT NULL, decision TEXT,
                    decided_by TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, time TEXT NOT NULL,
                    name TEXT NOT NULL, check_id TEXT NOT NULL,
                    actor_hash TEXT NOT NULL
                );
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        if self.blob_state:
            with self.blob_state.snapshot() as path:
                with closing(sqlite3.connect(path, timeout=10)) as db, db:
                    db.row_factory = sqlite3.Row
                    yield db
            return
        with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            yield db

    @staticmethod
    def timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def require_read(principal: Principal) -> None:
        if not principal.can_read:
            raise DemoError("Access denied: Finance pilot membership is required.", 403)

    def evidence(self, invoice_id: str) -> dict:
        invoice = next(
            (item for item in self.seed["invoices"] if item["id"] == invoice_id), None
        )
        if invoice is None:
            raise DemoError("Invoice not found.", 404)
        if invoice["department"] != "Finance":
            raise DemoError("Invoice is outside the Finance data boundary.", 403)
        contract = self.seed["contracts"][invoice["contract_id"]]
        expected = invoice["units"] * contract["unit_price_pence"]
        return {
            "invoice": invoice, "contract": contract, "policy": self.seed["policy"],
            "expected_pence": expected,
            "variance_pence": invoice["billed_pence"] - expected,
        }

    def event(self, db: sqlite3.Connection, name: str, check_id: str, actor: str) -> None:
        # No prompt, token, invoice content or raw user ID in usage telemetry.
        actor_hash = hashlib.sha256(actor.encode()).hexdigest()[:16]
        db.execute(
            "INSERT INTO events(time,name,check_id,actor_hash) VALUES(?,?,?,?)",
            (self.timestamp(), name, check_id, actor_hash),
        )

    def check(self, invoice_id: str, principal: Principal, source: str,
              request_id: str | None = None) -> dict:
        self.require_read(principal)
        evidence = self.evidence(invoice_id)
        check_id = request_id or secrets.token_hex(16)
        if not isinstance(check_id, str) or not 1 <= len(check_id) <= 100:
            raise DemoError("A request ID of 1-100 characters is required.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM checks WHERE id=?", (check_id,)).fetchone()
            if row:
                if row["invoice"] != invoice_id or row["source"] != source:
                    raise DemoError("Request ID already belongs to another request.", 409)
            else:
                db.execute(
                    "INSERT INTO checks(id,invoice,source,nonce,created_at) VALUES(?,?,?,?,?)",
                    (check_id, invoice_id, source, secrets.token_urlsafe(24), self.timestamp()),
                )
                self.event(db, "invoice_checked", check_id, principal.oid)
            row = db.execute("SELECT * FROM checks WHERE id=?", (check_id,)).fetchone()
        return self.card(dict(row), evidence)

    def anomalies_this_week(self, principal: Principal) -> list[dict]:
        self.require_read(principal)
        return [
            self.check(item["id"], principal, "chat")
            for item in self.seed["invoices"]
            if 0 <= item["age_days"] < 7 and self.evidence(item["id"])["variance_pence"] != 0
        ]

    def decide(self, check_id: str, nonce: str, action: str, principal: Principal) -> str:
        self.require_read(principal)
        if not principal.can_decide:
            raise DemoError("Access denied: a designated Finance approver is required.", 403)
        if action not in ("approve", "escalate"):
            raise DemoError("Unsupported decision.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM checks WHERE id=?", (check_id,)).fetchone()
            if row is None or not secrets.compare_digest(row["nonce"], str(nonce)):
                raise DemoError("Invalid or stale decision card.", 403)
            if row["decision"]:
                raise DemoError("This request already has a decision; refresh the invoice.", 409)
            created = datetime.fromisoformat(row["created_at"])
            if (datetime.now(timezone.utc) - created).total_seconds() > 3600:
                raise DemoError("Decision card expired; run a new check.", 409)
            if action == "approve" and self.evidence(row["invoice"])["variance_pence"] != 0:
                raise DemoError("CAL-POL-017 blocks approval of a variance. Escalate instead.", 409)
            db.execute(
                "UPDATE checks SET decision=?,decided_by=? WHERE id=?",
                (action, principal.oid, check_id),
            )
            self.event(db, f"human_{action}", check_id, principal.oid)
        return (
            f"{row['invoice']}: human decision '{action}' recorded in the synthetic "
            "Waypoint write boundary. No payment released."
        )

    def metrics(self) -> dict:
        with self.connection() as db:
            counts = dict(db.execute("SELECT name,count(*) FROM events GROUP BY name").fetchall())
            checked = db.execute("SELECT invoice FROM checks").fetchall()
        return {
            "label": "LOCAL SAMPLE TELEMETRY - NOT MICROSOFT AGENT 365",
            "events": counts,
            "checked_requests": len(checked),
            "flagged_requests": sum(self.evidence(row["invoice"])["variance_pence"] != 0 for row in checked),
            "payment_writes": 0,
        }

    @staticmethod
    def money(pence: int) -> str:
        return f"GBP {pence / 100:,.2f}"

    def card(self, row: dict, evidence: dict) -> dict:
        invoice = evidence["invoice"]
        variance = evidence["variance_pence"]
        heading = f"{invoice['id']} - " + (
            "Variance: escalate before approval" if variance else "No price variance detected"
        )
        facts = [
            {"title": "Billed", "value": self.money(invoice["billed_pence"])},
            {"title": "Contract total", "value": self.money(evidence["expected_pence"])},
            {"title": "Variance", "value": self.money(variance)},
        ]
        evidence_text = (
            f"Evidence: {invoice['contract_id']} clause {evidence['contract']['clause']}: "
            + evidence["contract"]["text"]
        )
        policy_text = (
            f"Policy: {evidence['policy']['id']} section {evidence['policy']['section']}: "
            + evidence["policy"]["text"]
        )
        decision_text = (
            "Human decision required. Approve records a synthetic workflow decision, "
            "not a payment. A variance cannot be approved."
        )
        fallback = "\n\n".join([
            "Waypoint | Caldova Pharmaceuticals | SYNTHETIC DATA",
            heading,
            "\n".join(f"{fact['title']}: {fact['value']}" for fact in facts),
            evidence_text,
            policy_text,
            decision_text,
            "If decision buttons are unavailable, open Waypoint in Teams and check "
            "this invoice there before deciding. No payment released.",
        ])
        return {
            "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard", "version": "1.4",
            "fallbackText": fallback,
            "body": [
                {"type": "TextBlock", "text": "Waypoint | Caldova Pharmaceuticals",
                 "weight": "Bolder", "wrap": True},
                {"type": "TextBlock", "text": "SYNTHETIC DATA",
                 "size": "Small", "wrap": True},
                {"type": "TextBlock", "text": heading, "weight": "Bolder",
                 "color": "Attention" if variance else "Good", "wrap": True},
                {"type": "FactSet", "facts": facts},
                {"type": "TextBlock", "text": evidence_text, "wrap": True},
                {"type": "TextBlock", "text": policy_text, "wrap": True},
                {"type": "TextBlock", "text": decision_text, "wrap": True},
            ],
            "actions": [
                {"type": "Action.Submit", "title": title, "data": {
                    "action": action, "check_id": row["id"], "nonce": row["nonce"],
                }}
                for title, action in (("Approve", "approve"), ("Escalate", "escalate"))
                if not variance or action == "escalate"
            ] if not row["decision"] else [],
        }
