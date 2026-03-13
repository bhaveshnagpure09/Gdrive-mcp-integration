# ============================================================
# start-dev.ps1  --  One-click local dev startup
# Usage:  .\start-dev.ps1
# Stop:   .\start-dev.ps1 -Stop
# ============================================================
param([switch]$Stop)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if ($Stop) {
    Write-Host "Stopping local dev services..." -ForegroundColor Yellow
    Get-Job -Name "api-dev" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job
    docker stop ib-job-skill-mapping-system-postgres-1 2>$null
    Write-Host "Done." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IB Job Skill Mapping -- Dev Startup   " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- 0. Kill stale Docker api/ui containers that conflict on ports 3000/8001 ----
Write-Host "[0/4] Clearing stale Docker containers (api, ui)..." -ForegroundColor DarkGray
docker stop ib-job-skill-mapping-system-api-1 ib-job-skill-mapping-system-ui-1 2>$null | Out-Null
docker rm   ib-job-skill-mapping-system-api-1 ib-job-skill-mapping-system-ui-1 2>$null | Out-Null
Write-Host "  Done." -ForegroundColor DarkGray

# -- 1. Start Postgres (default compose: localhost:5433) ----------------------
Write-Host ""
Write-Host "[1/4] Starting PostgreSQL on localhost:5433..." -ForegroundColor Yellow
docker compose up -d postgres --remove-orphans 2>&1 | Where-Object { $_ -notmatch "^time=" } | Out-Null

# Wait for pg_isready
$waited = 0
$ready  = $false
do {
    Start-Sleep -Seconds 2; $waited += 2
    $pgCheck = docker exec ib-job-skill-mapping-system-postgres-1 pg_isready -U user -d ib_job_skill_mapping 2>&1
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
} while ($waited -lt 30)

if (-not $ready) {
    Write-Host "  ERROR: Postgres not ready after 30s." -ForegroundColor Red; exit 1
}
Write-Host "  Postgres ready." -ForegroundColor Green

# -- 2. Alembic migrations ----------------------------------------------------
Write-Host ""
Write-Host "[2/4] Running Alembic migrations..." -ForegroundColor Yellow
$env:PYTHONPATH = "src"
$env:DATABASE_URL = "postgresql://user:password@localhost:5433/ib_job_skill_mapping"
$env:EMBEDDING_DEV_FALLBACK = "1"
$env:SKIP_RERANKER = "1"
$env:JWT_SECRET_KEY = "dev-secret"
$env:LOG_LEVEL = "INFO"
$env:VECTOR_STORE_DIR = "./data/faiss_index"

& "$Root\.venv\Scripts\alembic.exe" upgrade heads
if ($LASTEXITCODE -ne 0) { Write-Host "  ERROR: Migration failed." -ForegroundColor Red; exit 1 }
Write-Host "  Migrations applied." -ForegroundColor Green

# -- 3. Start API via background job (visible via Get-Job / Receive-Job) ------
Write-Host ""
Write-Host "[3/4] Starting API (uvicorn :8000)..." -ForegroundColor Yellow

# Kill any leftover job
Get-Job -Name "api-dev" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job

$apiJob = Start-Job -Name "api-dev" -ScriptBlock {
    param($Root)
    Set-Location $Root
    $env:PYTHONPATH = "src"
    $env:DATABASE_URL = "postgresql://user:password@localhost:5433/ib_job_skill_mapping"
    $env:EMBEDDING_DEV_FALLBACK = "1"
    $env:SKIP_RERANKER = "1"
    $env:JWT_SECRET_KEY = "dev-secret"
    $env:LOG_LEVEL = "INFO"
    $env:VECTOR_STORE_DIR = "./data/faiss_index"
    & "$Root\.venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port 8000 2>&1
} -ArgumentList $Root

# Wait for API to respond
$apiReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $apiReady = $true; break }
    } catch {}
}

if (-not $apiReady) {
    Write-Host "  ERROR: API did not start. Job output:" -ForegroundColor Red
    Receive-Job $apiJob | Select-Object -Last 20 | Write-Host
    exit 1
}

$h = (Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing).Content | ConvertFrom-Json
Write-Host "  API ready   -> http://localhost:8000" -ForegroundColor Green
Write-Host ("  API status  -> {0}" -f $h.status) -ForegroundColor Green
Write-Host ("  DB  status  -> {0}" -f $h.checks.database) -ForegroundColor Green

# -- 4. Start UI (Next.js :3000) in a new window -----------------------------
Write-Host ""
Write-Host "[4/4] Starting UI (Next.js :3000)..." -ForegroundColor Yellow

$uiEnvPath = Join-Path $Root "ui\.env.local"
Set-Content -Path $uiEnvPath -Value "NEXT_PUBLIC_API_URL=http://localhost:8000" -Encoding UTF8

$uiCmd = "Set-Location '$Root\ui'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $uiCmd -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "  UI window opened -> http://localhost:3000" -ForegroundColor Green

# -- Summary ------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Green
Write-Host ""
Write-Host ("  API  health  : {0}" -f $h.status.ToUpper()) -ForegroundColor $(if ($h.status -eq "healthy") {"Green"} else {"Red"})
Write-Host ("  DB   health  : {0}" -f $h.checks.database.ToUpper()) -ForegroundColor $(if ($h.checks.database -eq "healthy") {"Green"} else {"Red"})
Write-Host ""
Write-Host "  UI  -> http://localhost:3000" -ForegroundColor White
Write-Host "  API -> http://localhost:8000/docs" -ForegroundColor White
Write-Host "  DB  -> localhost:5433" -ForegroundColor White
Write-Host ""
Write-Host "  To view API logs:  Receive-Job api-dev" -ForegroundColor DarkGray
Write-Host "  To stop all:       .\start-dev.ps1 -Stop" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
