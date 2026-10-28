# One-command setup. Run this, wait, done.
#
#   .\setup.ps1              install packages, get data, build everything
#   .\setup.ps1 -Code        packages only, no download, no build
#   .\setup.ps1 -Fresh       delete .venv and the database first, start clean
#
# If a step fails the script stops and prints what to do about it, rather
# than carrying on and failing later somewhere less obvious.

param(
    [switch]$Code,
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Say($msg)  { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Good($msg) { Write-Host "    OK  $msg" -ForegroundColor Green }
function Die($msg, $fix) {
    Write-Host ""
    Write-Host "FAILED: $msg" -ForegroundColor Red
    if ($fix) { Write-Host ""; Write-Host "What to do:" -ForegroundColor Yellow; Write-Host $fix }
    exit 1
}

# --------------------------------------------------------------- 1. python
Say "Looking for Python 3.10 or newer"

$py = $null
foreach ($try in @(@("py","-3"), @("python",""), @("python3",""))) {
    $exe = $try[0]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    try {
        if ($try[1]) { $v = & $exe $try[1] -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null }
        else         { $v = & $exe        -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null }
    } catch { continue }
    if (-not $v) { continue }
    $parts = $v.Trim().Split(".")
    if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10) {
        $py = $try; Good "found Python $v"; break
    }
    Write-Host "    skip  $exe is Python $v (need 3.10+)"
}

if (-not $py) {
    Die "No Python 3.10 or newer found." @"
  Install Python from https://www.python.org/downloads/
  During install, TICK the box that says 'Add python.exe to PATH'.
  Then close this window, open a new one, and run .\setup.ps1 again.
"@
}

# --------------------------------------------------------------- 2. venv
if ($Fresh -and (Test-Path .venv)) {
    Say "Removing the old .venv (-Fresh)"
    Remove-Item .venv -Recurse -Force
}

$vpy = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path $vpy) {
    Say "Reusing the existing .venv"
} else {
    Say "Creating .venv"
    if ($py[1]) { & $py[0] $py[1] -m venv .venv } else { & $py[0] -m venv .venv }
    if (-not (Test-Path $vpy)) { Die "venv was not created." "Check you can write to $root" }
}

# A venv built from an UNSIGNED python (for example a uv-managed one) is
# blocked by Windows Smart App Control and dies with no message at all.
# Catch that here, where we can explain it, instead of three steps later.
$probe = & $vpy -c "print('alive')" 2>$null
if ($probe -ne "alive") {
    Die "The virtual environment will not start." @"
  This is almost always Windows Smart App Control blocking an unsigned
  Python. uv-managed Pythons are unsigned; the python.org installer is not.

  Fix:
    1. Install Python from https://www.python.org/downloads/
    2. Remove-Item .venv -Recurse -Force
    3. .\setup.ps1
"@
}
Good "virtual environment works"

# --------------------------------------------------------------- 3. packages
Say "Installing packages (about 1 minute)"
& $vpy -m pip install --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) { Die "Could not upgrade pip." "Check your internet connection or proxy settings." }

& $vpy -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Die "Package install failed." @"
  Most common causes:
    - no internet, or a proxy that needs configuring
    - a company mirror. Try:
        .venv\Scripts\python.exe -m pip install -r requirements.txt -i <your-mirror-url>
"@
}

& $vpy -c "import duckdb, yaml, httpx, networkx" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Die "Packages installed but will not import." "Run .\setup.ps1 -Fresh" }

$versions = & $vpy -c "import sys,duckdb,networkx;print('python %s | duckdb %s | networkx %s' % ('.'.join(map(str,sys.version_info[:3])), duckdb.__version__, networkx.__version__))"
Good $versions

if ($Code) {
    Write-Host ""
    Write-Host "Packages are installed. Data steps skipped (-Code)." -ForegroundColor Green
    Write-Host "Run .\setup.ps1 without -Code when you want the data."
    exit 0
}

# --------------------------------------------------------------- 4. data
$have = 0
if (Test-Path "data\raw") {
    $have = (Get-ChildItem "data\raw" -Recurse -Filter *.tar.gz -ErrorAction SilentlyContinue).Count
}

if ($have -ge 8) {
    Say "Data already downloaded ($have archives) - skipping"
} else {
    Say "Downloading the dataset (about 2 GB, a few minutes)"
    Write-Host "    This resumes if interrupted - just run setup again."
    & $vpy ingest\fetch.py --start 0d0 --minutes 9
    if ($LASTEXITCODE -ne 0) {
        Die "Download failed." @"
  Read the reason printed above each file - fetch.py now says exactly what
  went wrong (DNS, TLS, proxy, or a blocked domain) and what to set.

  Quick answers:

    Partial download, some files got through
        Run .\setup.ps1 again. It resumes, nothing is lost.

    Behind a corporate proxy
        `$env:HTTPS_PROXY = "http://user:pass@proxy.company.com:8080"
        `$env:HTTP_PROXY  = `$env:HTTPS_PROXY
        .\setup.ps1

    Company inspects TLS (CERTIFICATE_VERIFY_FAILED)
        `$env:SSL_CERT_FILE = "C:\path\to\company-ca.pem"
        .\setup.ps1
      or, accepting the risk on a corporate network:
        .venv\Scripts\python.exe ingest\fetch.py --start 0d0 --minutes 9 --insecure
        .\setup.ps1

    Nothing works - the network simply will not allow it
        You do not have to download anything. Copy the `data\raw` folder
        from a machine that already has it into this project, then run
        .\setup.ps1 again. It will find the archives and skip this step.
"@
    }
}
Good "dataset present"

# --------------------------------------------------------------- 5. build
if ($Fresh -and (Test-Path "data\okg.duckdb")) {
    Remove-Item "data\okg.duckdb" -Force
}

Say "Creating tables"
& $vpy graph\apply_schema.py --reset
if ($LASTEXITCODE -ne 0) { Die "Could not create the tables." "Close any other program using data\okg.duckdb - DuckDB allows one writer." }

Say "Loading the CSV data (about 2 minutes)"
Write-Host "    Roughly 3,000 rows will be rejected as malformed. That is correct -"
Write-Host "    they are quarantined with a reason, not silently dropped."
& $vpy ingest\load.py --all
if ($LASTEXITCODE -ne 0) { Die "Load failed." "If it ran out of memory, try: .venv\Scripts\python.exe ingest\load.py --table CallGraph --limit 1" }

Say "Building the knowledge graph (about 6 minutes)"
& $vpy graph\build.py --facts
if ($LASTEXITCODE -ne 0) { Die "Build failed." "Read the error above - it names the SQL statement that failed." }

Say "Deriving team ownership"
& $vpy ingest\derive_teams.py
if ($LASTEXITCODE -ne 0) { Die "Team derivation failed." "" }

# --------------------------------------------------------------- 6. prove it
Say "Checking the rules"
# Severity 1 and 2 only. Severity 3 is report-only, and one of those rules
# (closure_truncated_at_cap) walks the whole call graph to a depth cap -
# about 7 minutes, half the total setup time, to produce a number nobody
# needs during install. The full pass is one command away and is named below.
& $vpy ontology\validate.py --stage graph --max-severity 2
if ($LASTEXITCODE -ne 0) { Die "A severity-1 rule failed - the graph is wrong." "Read the sample rows printed above; they name the exact bad rows." }
Write-Host "    (severity-3 rules skipped to save ~7 min. Full check:"
Write-Host "     .venv\Scripts\python.exe ontology\validate.py --stage graph)"

Say "Verifying every number"
& $vpy verify.py
if ($LASTEXITCODE -ne 0) { Die "A check failed." "Read which one above. This is the safety net working." }

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host " DONE. Everything is installed and verified." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Try it:"
Write-Host "  .venv\Scripts\python.exe semantic\compile.py --list"
Write-Host "  .venv\Scripts\python.exe semantic\compile.py rt_p99 --by microservice --limit 5"
Write-Host "  .venv\Scripts\python.exe verify.py --only travel"
Write-Host ""
Write-Host "SETUP.md explains each step if you want to run them by hand."
