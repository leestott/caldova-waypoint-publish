import contextlib
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_public
import export


class ExportTests(unittest.TestCase):
    def prepare(self, root):
        for name in check_public.TOP_FILES:
            (root / name).write_text("portable example\n")
        workflow = root / ".github" / "workflows" / "validate-waypoint.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: Test\n")
        for name in ("waypoint/core.py", "data/seed.json", "docs/guide.md",
                     "docs/.env", "docs/secrets.json", "docs/state/record.json",
                     ".env", ".venv/secret.py", "dist/deployment.json",
                     "dist/tenant/waypoint.zip"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")

    def test_default_archive_never_copies_tenant_package_or_nested_private_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "sample"
            root.mkdir()
            self.prepare(root)
            output = Path(directory) / "output"
            with patch.object(export, "ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                archive = export.export(output)
            with ZipFile(archive) as package:
                names = {name.removeprefix("caldova-waypoint-publish/") for name in package.namelist()}
            self.assertTrue({"LICENSE", ".env.example", "waypoint/core.py"} <= names)
            self.assertFalse({".env", "docs/.env", "docs/secrets.json", "docs/state/record.json"} & names)
            self.assertFalse(any(name.startswith(("dist/", ".venv/")) for name in names))
            self.assertFalse((output / "waypoint-tenant-package.zip").exists())

    def test_private_package_requires_explicit_flag(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "sample"
            root.mkdir()
            self.prepare(root)
            with patch.object(export, "ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                export.export(Path(directory) / "output", include_tenant_package=True)
            self.assertTrue((Path(directory) / "output" / "waypoint-tenant-package.zip").exists())

    def test_known_private_values_fail_without_disclosing_value(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepare(root)
            private = "private-subscription-fixture"
            (root / ".env").write_text(f"AZURE_SUBSCRIPTION_ID={private}\n")
            (root / "docs" / "guide.md").write_text(private)
            with self.assertRaises(ValueError) as error:
                check_public.check_files(check_public.source_files(root), root)
            self.assertIn("AZURE_SUBSCRIPTION_ID", str(error.exception))
            self.assertNotIn(private, str(error.exception))

    def test_missing_license_blocks_release(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepare(root)
            (root / "LICENSE").unlink()
            with self.assertRaisesRegex(ValueError, "LICENSE"):
                check_public.check_files(check_public.source_files(root), root)
