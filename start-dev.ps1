# ============================================================
# start-dev.ps1  —  One-click local dev startup
#
# Starts: PostgreSQL (Docker) → Alembic migrations → API (uvicorn) → UI (Next.js)
#
# Usage:  .\start-dev.ps1
# Stop:   Ctrl+C in each window, then:  docker compose down
# ============================================================

$Root = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  IB Job Skill Mapping — Dev Startup    " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Start Postgres ────────────────────────────────────────
Write-Host "[1/4] Starting PostgreSQL (Docker)..." -ForegroundColor Yellow
Set-Location $Root
docker compose up -d postgres | Out-Null

# Wait for healthy (Docker health status OR direct pg_isready)
$maxWait = 30
$waited  = 0
$ready   = $false
do {
    Start-Sleep -Seconds 2
    $waited += 2
    $status = docker inspect --format="{{.State.Health.Status}}" ib-job-skill-mapping-system-postgres-1 2>$null
    if ($status -eq "healthy") { $ready = $true; break }
    # Fallback: direct port check via pg_isready inside container
    $pgCheck = docker exec ib-job-skill-mapping-system-postgres-1 pg_isready -U user -d ib_job_skill_mapping 2>$null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
} while ($waited -lt $maxWait)

if (-not $ready) {
    Write-Host "  ERROR: Postgres did not become ready after ${maxWait}s. Check Docker." -ForegroundColor Red
    exit 1
}
Write-Host "  Postgres is healthy on localhost:5433" -ForegroundColor Green

# ── 2. Run Alembic migrations ────────────────────────────────
Write-Host ""
Write-Host "[2/4] Running Alembic migrations..." -ForegroundColor Yellow
$env:PYTHONPATH      = "src"
$env:DATABASE_URL    = "postgresql://user:password@localhost:5433/ib_job_skill_mapping"
$env:EMBEDDING_DEV_FALLBACK = "1"
$env:SKIP_RERANKER   = "1"
$env:JWT_SECRET_KEY  = "dev-secret"

& "$Root\.venv\Scripts\alembic.exe" upgrade heads
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Alembic migration failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Migrations applied." -ForegroundColor Green

# ── 3. Start API (uvicorn) in a new window ───────────────────
Write-Host ""
Write-Host "[3/4] Starting API (uvicorn on :8000)..." -ForegroundColor Yellow

$apiCmd = @"
`$env:PYTHONPATH='src'
`$env:DATABASE_URL='postgresql://user:password@localhost:5433/ib_job_skill_mapping'
`$env:EMBEDDING_DEV_FALLBACK='1'
`$env:SKIP_RERANKER='1'
`$env:JWT_SECRET_KEY='dev-secret'
`$env:LOG_LEVEL='INFO'
`$env:VECTOR_STORE_DIR='./data/faiss_index'
Set-Location '$Root'
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCmd -WindowStyle Normal

# Wait for API to respond
Write-Host "  Waiting for API to be ready..." -ForegroundColor DarkGray
$apiReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $apiReady = $true; break }
    } catch { }
}

if ($apiReady) {
    Write-Host "  API is ready at http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "  WARNING: API did not respond in time — check the API window for errors." -ForegroundColor DarkYellow
}

# ── 4. Start UI (Next.js) in a new window ───────────────────
Write-Host ""
Write-Host "[4/4] Starting UI (Next.js on :3000)..." -ForegroundColor Yellow

$uiCmd = "Set-Location '$Root\ui'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $uiCmd -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host "  UI starting at http://localhost:3000" -ForegroundColor Green

# ── Summary ─────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "  UI  →  http://localhost:3000" -ForegroundColor White
Write-Host "  API →  http://localhost:8000" -ForegroundColor White
Write-Host "  DB  →  localhost:5433" -ForegroundColor White
Write-Host ""
Write-Host "  To stop: Ctrl+C in each window, then:" -ForegroundColor DarkGray
Write-Host "           docker compose down" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
