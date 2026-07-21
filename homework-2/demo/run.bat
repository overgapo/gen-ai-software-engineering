@echo off
rem One-command demo for Windows: install, build the front-end, start the
rem server and seed it with sample data. Run from the repo: demo\run.bat
setlocal
set ROOT=%~dp0..
if "%PORT%"=="" set PORT=3000

echo ==^> Installing backend dependencies
pushd "%ROOT%" && call npm install --silent && popd

echo ==^> Installing front-end dependencies and building
pushd "%ROOT%\client" && call npm install --silent && call npm run build --silent && popd

echo ==^> Starting server on port %PORT%
start "support-api" /b cmd /c "cd /d %ROOT% && set PORT=%PORT% && node src\server.js"

echo ==^> Waiting for the server
timeout /t 3 /nobreak > nul

echo ==^> Seeding sample data (with auto-classification)
for %%f in (sample_tickets.csv sample_tickets.json sample_tickets.xml) do (
  curl -s -X POST "http://localhost:%PORT%/tickets/import?auto_classify=true" -F "file=@%ROOT%\demo\%%f"
  echo.
)

echo.
echo ==^> Demo of the all-or-nothing import (this one is expected to fail):
curl -s -X POST "http://localhost:%PORT%/tickets/import" -F "file=@%ROOT%\demo\invalid_tickets.csv"
echo.

echo.
echo ==^> Ready: open http://localhost:%PORT% in your browser
pause
