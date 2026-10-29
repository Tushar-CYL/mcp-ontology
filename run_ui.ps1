# Start the demo UI, with no stale server left behind.
#
# Streamlit re-runs app.py on every interaction but does NOT re-import the
# modules it depends on. So a server started before a change to
# knowledge_graph/ or ontology/ keeps serving the OLD code and reports an
# ImportError for anything added since. Restarting is the fix, and killing
# the previous one first is the part that is easy to forget.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$old = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
         Where-Object { $_.CommandLine -like '*streamlit*' })
if ($old.Count) {
    Write-Host "Stopping $($old.Count) running app(s)..." -ForegroundColor Yellow
    $old | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 2
}

Write-Host "Starting on http://localhost:8501" -ForegroundColor Green
& .\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8501
