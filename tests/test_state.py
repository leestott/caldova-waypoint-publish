from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from azure.core.exceptions import ResourceExistsError

from waypoint.core import Principal, Waypoint
from waypoint.state import BlobState


class FakeBlob:
    def __init__(self):
        self.content = None
        self.leased = False
        self.fail_upload = False

    def upload_blob(self, source, overwrite=False, lease=None):
        if not overwrite and self.content is not None:
            raise ResourceExistsError("Already initialized")
        if overwrite:
            assert self.leased and lease is self
        if self.fail_upload:
            raise RuntimeError("Synthetic storage failure")
        self.content = source if isinstance(source, bytes) else source.read()

    def acquire_lease(self, lease_duration):
        assert lease_duration == 60 and not self.leased
        self.leased = True
        return self

    def release(self):
        self.leased = False

    def download_blob(self, lease):
        assert self.leased and lease is self
        return self

    def readall(self):
        return self.content


class BlobStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.blob = FakeBlob()
        self.env = patch.dict(os.environ, {
            "WAYPOINT_STATE_BLOB_URL": "https://example.blob.core.windows.net/private/state",
            "AZURE_CLIENT_ID": "synthetic-managed-identity",
            "WAYPOINT_DATABASE": str(Path(self.temp.name) / "unused.sqlite3"),
        })
        self.env.start()
        self.identity = patch("waypoint.state.ManagedIdentityCredential")
        self.client = patch("waypoint.state.BlobClient.from_blob_url", return_value=self.blob)
        self.identity.start()
        self.client.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.env.stop)
        self.addCleanup(self.identity.stop)
        self.addCleanup(self.client.stop)

    def test_snapshot_persists_decisions_across_engine_instances(self):
        actor = Principal("test-babak", True, True)
        engine = Waypoint()
        card = engine.check("INV-1042", actor, "chat")
        action = card["actions"][0]["data"]
        Waypoint().decide(action["check_id"], action["nonce"], "escalate", actor)
        self.assertEqual(Waypoint().metrics()["events"]["human_escalate"], 1)
        self.assertFalse(self.blob.leased)

    def test_failed_operation_keeps_snapshot_and_releases_lease(self):
        store = BlobState(os.environ["WAYPOINT_STATE_BLOB_URL"])
        before = self.blob.content
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with store.snapshot() as path:
                path.write_bytes(b"must not be committed")
                raise RuntimeError("abort")
        self.assertEqual(self.blob.content, before)
        self.assertFalse(self.blob.leased)

    def test_failed_upload_is_not_reported_as_a_success(self):
        engine = Waypoint()
        before = self.blob.content
        self.blob.fail_upload = True
        with self.assertRaisesRegex(RuntimeError, "storage failure"):
            engine.check("INV-1042", Principal("test-babak", True, True), "chat")
        self.assertEqual(self.blob.content, before)
        self.assertFalse(self.blob.leased)
