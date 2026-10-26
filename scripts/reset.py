from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
database = ROOT / "state" / "waypoint.sqlite3"
if database.exists():
    database.unlink()
print("Synthetic decisions and telemetry reset. Stop the server before running this command.")
