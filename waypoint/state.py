"""Lease-protected SQLite snapshots for the small, single-replica synthetic demo."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from azure.core.exceptions import ResourceExistsError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobClient


class BlobState:
    def __init__(self, url: str):
        credential = ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"])
        self.blob = BlobClient.from_blob_url(
            url, credential=credential, connection_timeout=10, read_timeout=15, retry_total=1,
        )
        try:
            self.blob.upload_blob(b"", overwrite=False)
        except ResourceExistsError:
            pass

    @contextmanager
    def snapshot(self):
        # All readers/writers use the same server-enforced lease. Never disable
        # SQLite locks on a network share or acknowledge a failed snapshot write.
        lease = self.blob.acquire_lease(lease_duration=60)
        try:
            with tempfile.TemporaryDirectory(prefix="waypoint-state-") as folder:
                path = Path(folder) / "waypoint.sqlite3"
                path.write_bytes(self.blob.download_blob(lease=lease).readall())
                yield path
                with path.open("rb") as source:
                    self.blob.upload_blob(source, overwrite=True, lease=lease)
        finally:
            lease.release()
