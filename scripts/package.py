"""Validate the official manifest schema, generate app icons, and create the ZIP."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import UUID
from zipfile import ZipFile

from dotenv import load_dotenv
from jsonschema import validators, FormatChecker
from jsonschema.exceptions import ValidationError
from PIL import Image, ImageDraw
import regex

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_URL = "https://developer.microsoft.com/json-schemas/teams/v1.30/MicrosoftTeams.schema.json"
DEMO = {
    "APP_ID": "7cb46a2f-dfce-4d7b-8b47-8d59b88fc749",
    "BOT_ID": "3d743cc8-1fe3-4ff5-9fd7-b527d0d88e52",
    "BOT_DOMAIN": "waypoint.example.com",
    "APP_BASE_URL": "https://waypoint.example.com",
}


def unicode_pattern(validator, pattern, instance, schema):
    if isinstance(instance, str) and not regex.search(pattern, instance):
        yield ValidationError(f"{instance!r} does not match {pattern!r}")


def render(values: dict, compatibility: bool = False) -> dict:
    for key in DEMO:
        if not values.get(key) or "[Confirm]" in values[key]:
            raise ValueError(f"{key} must be configured.")
    for key in ("APP_ID", "BOT_ID"):
        UUID(values[key])
    parsed = urlparse(values["APP_BASE_URL"])
    if (parsed.scheme != "https" or parsed.netloc != values["BOT_DOMAIN"]
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("APP_BASE_URL must be an HTTPS origin matching BOT_DOMAIN.")
    text = (ROOT / "appPackage" / "manifest.template.json").read_text()
    for key in DEMO:
        # JSON encoding prevents configuration values from injecting manifest fields.
        text = text.replace("{{" + key + "}}", json.dumps(values[key])[1:-1])
    if re.search(r"\{\{.+?\}\}", text):
        raise ValueError("Unresolved manifest placeholders.")
    manifest = json.loads(text)
    if compatibility:
        manifest["manifestVersion"] = "1.24"
        manifest["$schema"] = SCHEMA_URL.replace("/v1.30/", "/v1.24/")
        for commands in manifest["bots"][0]["commandLists"]:
            for command in commands["commands"]:
                prompt = command.pop("prompt")
                command.pop("type")
                command["title"] = (
                    "Check invoice INV-1042" if prompt.startswith("Check invoice") else prompt
                )
    return manifest


def icon(size: int, outline: bool, destination: Path) -> None:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0) if outline else "#0A6BBA")
    draw = ImageDraw.Draw(image)
    # An original app monogram, not a Microsoft product logo or a Caldova brand asset.
    points = [(size * x, size * y) for x, y in (
        (.21, .27), (.34, .73), (.50, .43), (.66, .73), (.79, .27)
    )]
    draw.line(points, fill="white", width=max(2, size // 13), joint="curve")
    image.save(destination)


def build(demo: bool, compatibility: bool = False) -> Path:
    load_dotenv(ROOT / ".env")
    values = DEMO if demo else {key: os.getenv(key, "") for key in DEMO}
    if not demo and any(value in DEMO.values() for value in values.values()):
        raise ValueError("Demo identifiers/domains cannot be used for a tenant upload.")
    manifest = render(values, compatibility)
    folder = ROOT / "dist" / ("demo" if demo else "tenant")
    folder.mkdir(parents=True, exist_ok=True)
    # Validation must fail when schema retrieval fails; never silently downgrade.
    with urlopen(manifest["$schema"], timeout=30) as response:
        schema = json.load(response)
    validator = validators.extend(validators.validator_for(schema), {"pattern": unicode_pattern})
    # The official schema uses Unicode property escapes (\p{L}); Python's re
    # cannot parse those. Use regex for patterns, including metaschema checks.
    formats = FormatChecker()
    formats.checks("regex", raises=regex.error)(lambda value: bool(regex.compile(value)))
    validator.check_schema(schema, format_checker=formats)
    validator(schema, format_checker=formats).validate(manifest)
    (folder / "MicrosoftTeams.schema.json").write_text(json.dumps(schema))
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    icon(192, False, folder / "color.png")
    icon(32, True, folder / "outline.png")
    package = folder / ("waypoint-DEMO-NOT-FOR-UPLOAD.zip" if demo else "waypoint.zip")
    with ZipFile(package, "w") as archive:
        for name in ("manifest.json", "color.png", "outline.png"):
            archive.write(folder / name, name)
    print(f"Official schema validated; package: {package}")
    if demo:
        print("DEMO IDs only. This is not an uploadable tenant package.")
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="CI/local package, not for tenant upload")
    parser.add_argument("--compatibility", action="store_true",
                        help="Use v1.24 command-menu starters instead of v1.30 typed prompts")
    args = parser.parse_args()
    build(args.demo, args.compatibility)
