"""Export portable source; configured tenant packages require an explicit opt-in."""
import argparse
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from check_public import check_files, source_files

ROOT = Path(__file__).resolve().parent.parent


def export(destination: Path, include_tenant_package: bool = False):
    files = source_files(ROOT)
    check_files(files, ROOT)
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / "caldova-waypoint-publish.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr("caldova-waypoint-publish/" + name, content)
    if include_tenant_package:
        package = ROOT / "dist" / "tenant" / "waypoint.zip"
        if not package.is_file():
            raise FileNotFoundError("No configured tenant package exists; source export remains portable.")
        shutil.copy2(package, destination / "waypoint-tenant-package.zip")
        print("Explicit operator-only tenant package exported separately. Do not publish it as the generic sample.")
    print(f"Portable source export: {archive_path}")
    return archive_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--include-tenant-package", action="store_true",
                        help="Explicitly copy the configured private-tenant ZIP separately; never use for a public release.")
    args = parser.parse_args()
    export(args.destination, args.include_tenant_package)
