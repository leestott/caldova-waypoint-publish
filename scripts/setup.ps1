$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
    & .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & .\.venv\Scripts\python.exe scripts\initialize.py
    if ($LASTEXITCODE -ne 0) { throw 'Local configuration initialization failed.' }
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & .\.venv\Scripts\python.exe scripts\package.py --demo
    if ($LASTEXITCODE -ne 0) { throw 'Manifest validation/packaging failed.' }
    & .\.venv\Scripts\python.exe -m waypoint.demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo failed.' }
} finally {
    Pop-Location
}
