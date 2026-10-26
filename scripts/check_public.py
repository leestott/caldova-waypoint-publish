"""Fail closed on private configuration and credential-like release content."""
import re
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
TOP_FILES = {".env.example", ".gitignore", ".dockerignore", "Dockerfile", "README.md",
             "requirements.txt", "LICENSE", "NOTICE.md"}
EXTENSIONS = {"appPackage": {".json"}, "data": {".json"}, "docs": {".md", ".json"},
              "scripts": {".py", ".ps1"}, "tests": {".py"}, "waypoint": {".py"}}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "signed URL": re.compile(r"[?&]sig=[A-Za-z0-9%+/=]{15,}"),
    "personal SharePoint link": re.compile(r"https://[^\s)]+sharepoint\.com/[^\s)]*personal/", re.I),
}


def source_files(root: Path):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or "__pycache__" in relative.parts:
            continue
        if any(part.lower() in {"dist", "state", "operator-records", "credentials", "secrets"}
               or part.lower().startswith((".env", ".git", ".venv"))
               for part in relative.parts) and relative.as_posix() not in TOP_FILES:
            continue
        if path.stem.lower() in {"credentials", "secrets", "deployment", "tokens"}:
            continue
        if relative.parts[0] not in EXTENSIONS:
            if relative.as_posix() not in TOP_FILES:
                continue
        elif path.suffix not in EXTENSIONS[relative.parts[0]]:
            continue
        if root.resolve() not in path.resolve().parents:
            raise ValueError(f"Source file resolves outside the sample: {relative}")
        if any(part.startswith(".env") for part in relative.parts) and relative.as_posix() != ".env.example":
            raise ValueError(f"Private environment file in a source directory: {relative}")
        result[relative.as_posix()] = path.read_bytes()
    local = root / ".github" / "workflows" / "validate-waypoint.yml"
    workflow = local if local.is_file() else root.parent / ".github" / "workflows" / "validate-waypoint.yml"
    if workflow.is_file():
        text = workflow.read_text()
        if workflow != local:
            text = text.replace(
                "paths: ['caldova-waypoint-publish/**', '.github/workflows/validate-waypoint.yml']",
                "paths: ['**']",
            ).replace("    defaults:\n      run:\n        working-directory: caldova-waypoint-publish\n", "")
            text = text.replace("caldova-waypoint-publish/", "")
        result[".github/workflows/validate-waypoint.yml"] = text.encode()
    return result


def check_files(files, root=ROOT):
    required = {"LICENSE", "NOTICE.md", ".env.example", "README.md", ".github/workflows/validate-waypoint.yml"}
    if missing := required - set(files):
        raise ValueError(f"Public source is missing required files: {sorted(missing)}")
    private = dotenv_values(root / ".env") if (root / ".env").is_file() else {}
    private_keys = (
        "AZURE_SUBSCRIPTION_ID", "TENANT_ID", "DEPLOYMENT_USER_PRINCIPAL_NAME",
        "FLOW_SHARED_SECRET", "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET",
        "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID", "BOT_ID", "APP_ID",
        "BOT_DOMAIN", "APP_BASE_URL",
    )
    failures = []
    for name, content in files.items():
        text = content.decode("utf-8-sig")
        for number, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    failures.append(f"{name}:{number}: {label}")
            for key in private_keys:
                value = private.get(key)
                if value and len(value) >= 8 and value.lower() in line.lower():
                    failures.append(f"{name}:{number}: private {key} value")
            if name.endswith(".md") and "Microsoft Confidential" in line:
                failures.append(f"{name}:{number}: internal-only document marking")
    if failures:
        raise ValueError("Public export blocked (values withheld):\n" + "\n".join(failures))
    print(f"Public source checks passed for {len(files)} files. This is not a full security audit.")


if __name__ == "__main__":
    check_files(source_files(ROOT))
