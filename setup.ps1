# One-time setup on Windows. Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "== Backend: Python virtual environment and packages ==" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Installing Docling (PDF/DOCX extraction, large download - first time only)..."
.\.venv\Scripts\python.exe -m pip install -r requirements-docling.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env from .env.example - put your GEMINI_API_KEY in it." -ForegroundColor Yellow
}
.\.venv\Scripts\python.exe -m app.cli init-keys
.\.venv\Scripts\python.exe -m app.cli gen-cert
.\.venv\Scripts\python.exe -m app.cli seed

Write-Host "== Frontend: npm packages ==" -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install

Set-Location $root
Write-Host "Setup complete. Start the app with .\start-backend.ps1 and .\start-frontend.ps1 (two terminals)." -ForegroundColor Green
