# Starts the web app on https://localhost:5173 (proxies /api to the backend)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\frontend"
npm run dev
