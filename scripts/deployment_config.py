"""Operator-owned deployment configuration; never infer a tenant or account."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from uuid import UUID

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class DeploymentSettings:
    subscription: str
    tenant: str
    operator: str
    resource_group: str
    location: str
    prefix: str
    names: dict[str, str]

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env")
        subscription = os.getenv("AZURE_SUBSCRIPTION_ID", "").strip().lower()
        tenant = os.getenv("TENANT_ID", "").strip().lower()
        group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
        prefix = os.getenv("DEPLOYMENT_PREFIX", "waypoint").strip()
        suffix = hashlib.sha256(f"{subscription}/{tenant}/{group}".encode()).hexdigest()[:8]
        defaults = {
            "AZURE_BOT_NAME": f"{prefix}-bot",
            "AZURE_CONTAINER_APP_NAME": f"{prefix}-agent",
            "AZURE_CONTAINER_ENVIRONMENT": f"{prefix}-environment",
            "AZURE_CONTAINER_REGISTRY": f"{prefix.replace('-', '')}registry{suffix}",
            "AZURE_STORAGE_ACCOUNT": f"{prefix.replace('-', '')}state{suffix}",
            "AZURE_MANAGED_IDENTITY_NAME": f"{prefix}-identity",
            "AZURE_WORKFLOW_NAME": f"{prefix}-invoice-approval",
            "AZURE_TEAMS_CONNECTION_NAME": f"{prefix}-teams",
            "APP_REGISTRATION_NAME": f"{prefix}-invoice-assurance",
            "FINANCE_PILOT_GROUP_NAME": f"{prefix} Finance Pilot",
            "FINANCE_TEAM_NAME": f"Caldova {prefix} Finance",
            "FINANCE_CHANNEL_NAME": "Finance Approvals",
            "BOT_OAUTH_CONNECTION_NAME": "teams_sso",
            "BOT_TOKEN_STORE_NAME": f"{prefix}-token-store",
            "AZURE_WEB_APP_NAME": "",
            "AZURE_APP_SERVICE_PLAN": "",
        }
        return cls(
            subscription, tenant, os.getenv("DEPLOYMENT_USER_PRINCIPAL_NAME", "").strip().lower(),
            group, os.getenv("AZURE_LOCATION", "").strip().lower(), prefix,
            {key: os.getenv(key, "").strip() or value for key, value in defaults.items()},
        )

    def validate(self):
        for name, value in (("AZURE_SUBSCRIPTION_ID", self.subscription), ("TENANT_ID", self.tenant)):
            try:
                UUID(value)
            except ValueError:
                raise ValueError(f"Set {name} to your own GUID in .env.") from None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+", self.operator):
            raise ValueError("Set DEPLOYMENT_USER_PRINCIPAL_NAME explicitly in .env.")
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,9}", self.prefix):
            raise ValueError("DEPLOYMENT_PREFIX must be 3-10 lowercase letters/digits/hyphens.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,90}", self.resource_group):
            raise ValueError("Set AZURE_RESOURCE_GROUP to a dedicated resource group in .env.")
        if not re.fullmatch(r"[a-z0-9]+", self.location):
            raise ValueError("Set AZURE_LOCATION to an Azure region name in .env.")
        for key in ("AZURE_BOT_NAME", "AZURE_CONTAINER_APP_NAME", "AZURE_CONTAINER_ENVIRONMENT",
                    "AZURE_MANAGED_IDENTITY_NAME", "AZURE_WORKFLOW_NAME", "AZURE_TEAMS_CONNECTION_NAME"):
            if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}[a-z0-9]", self.names[key]):
                raise ValueError(f"{key} must be a 3-32 character lowercase resource name.")
        for key, maximum in (("AZURE_STORAGE_ACCOUNT", 24), ("AZURE_CONTAINER_REGISTRY", 50)):
            if not re.fullmatch(rf"[a-z0-9]{{3,{maximum}}}", self.names[key]):
                raise ValueError(f"{key} must be 3-{maximum} lowercase alphanumeric characters.")

    def identity(self):
        return {"subscription_id": self.subscription, "tenant_id": self.tenant,
                "resource_group": self.resource_group, "region": self.location}


def finance_oids(operator_oid):
    pilots = {x.strip().lower() for x in os.getenv("FINANCE_PILOT_OIDS", "").split(",") if x.strip()}
    approvers = {x.strip().lower() for x in os.getenv("FINANCE_APPROVER_OIDS", "").split(",") if x.strip()}
    pilots = pilots or {operator_oid.lower()}
    approvers = approvers or {operator_oid.lower()}
    for oid in pilots | approvers:
        UUID(oid)
    if not approvers <= pilots:
        raise ValueError("FINANCE_APPROVER_OIDS must be a subset of FINANCE_PILOT_OIDS.")
    return sorted(pilots), sorted(approvers)
