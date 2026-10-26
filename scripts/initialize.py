from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent.parent
target = ROOT / ".env"
if not target.exists():
    text = (ROOT / ".env.example").read_text()
    text = text.replace("FLOW_SHARED_SECRET=\n", f"FLOW_SHARED_SECRET={secrets.token_urlsafe(48)}\n")
    target.write_text(text)
    print("Created untracked local .env with a random workflow credential.")
else:
    print("Existing .env preserved.")
