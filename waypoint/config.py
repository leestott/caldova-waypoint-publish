from dataclasses import dataclass
import os
from uuid import UUID

from dotenv import load_dotenv
from .core import DemoError, Principal, ROOT


@dataclass(frozen=True)
class Settings:
    mode: str
    flow_secret: str
    tenant_id: str
    pilots: frozenset[str]
    approvers: frozenset[str]
    channel_id: str

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        mode = os.getenv("WAYPOINT_MODE", "local")
        if mode not in ("local", "tenant"):
            raise ValueError("WAYPOINT_MODE must be local or tenant.")
        secret = os.getenv("FLOW_SHARED_SECRET", "")
        if len(secret) < 32:
            raise ValueError("FLOW_SHARED_SECRET must contain at least 32 random characters.")
        pilots = frozenset(x.strip().lower() for x in os.getenv("FINANCE_PILOT_OIDS", "").split(",") if x.strip())
        approvers = frozenset(x.strip().lower() for x in os.getenv("FINANCE_APPROVER_OIDS", "").split(",") if x.strip())
        tenant = os.getenv("TENANT_ID", "").lower()
        channel = os.getenv("FINANCE_CHANNEL_ID", "")
        if mode == "tenant":
            UUID(tenant)
            for oid in pilots | approvers:
                UUID(oid)
            if not pilots or not approvers or not approvers <= pilots or not channel:
                raise ValueError("Tenant mode requires pilot/approver OIDs and a Finance channel; approvers must be pilots.")
            for key in ("CLIENTID", "CLIENTSECRET", "TENANTID"):
                if not os.getenv(f"CONNECTIONS__SERVICE_CONNECTION__SETTINGS__{key}"):
                    raise ValueError(f"Missing service connection {key}.")
            if os.environ["CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID"].lower() != tenant:
                raise ValueError("Service connection tenant must match TENANT_ID.")
        return cls(mode, secret, tenant, pilots, approvers, channel)

    def principal(self, oid: str) -> Principal:
        oid = oid.lower()
        if self.mode == "local":
            if oid != "local-babak":
                raise DemoError("Local demo accepts only its labelled synthetic actor.", 403)
            return Principal(oid, True, True)
        return Principal(oid, oid in self.pilots, oid in self.approvers)
