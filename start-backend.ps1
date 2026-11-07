# Starts the API on https://localhost:8000 (API docs at https://localhost:8000/docs)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"
.\.venv\Scripts\python.exe run.py
