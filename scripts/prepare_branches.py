"""Create a separate disposable rehearsal repo; never switch this worktree."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
target = ROOT / "dist" / "caldova-waypoint-publish"
if target.exists():
    raise SystemExit(f"Refusing to overwrite {target}. Choose a fresh export location in this script.")
target.mkdir(parents=True)


def git(*args):
    subprocess.run(["git", "-C", str(target), *args], check=True, capture_output=True)


git("init", "-b", "demo/01-existing")
git("config", "user.name", "Caldova demo preparation")
git("config", "user.email", "demo@example.invalid")
for name in ("data", "waypoint"):
    shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "server.py", "config.py"))
git("add", ".")
git("commit", "-m", "Existing synthetic Waypoint evidence and write boundary\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>")
git("switch", "-c", "demo/02-publish")
for item in ROOT.iterdir():
    if item.name in (".env", ".venv", "dist", "state", "__pycache__"):
        continue
    if item.is_dir():
        shutil.copytree(item, target / item.name, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        shutil.copy2(item, target / item.name)
git("add", ".")
git("commit", "-m", "Prepared Microsoft 365 publishing adapter and package\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>")
print(f"Prepared independent rehearsal branches in {target}")
print("Open this folder in VS Code. No branch in the parent repository was changed.")
