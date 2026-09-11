# PaperLingo Windows build script.
# uv drives the whole flow: checks -> sync -> tests -> clean -> PyInstaller -> verify exe.
# Usage (PowerShell): .\scripts\build.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Fail([string]$msg) {
    Write-Host $msg -ForegroundColor Red
    exit 1
}

Write-Host "==> Checking uv ..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "uv not found. Install it first: https://docs.astral.sh/uv/"
}
uv --version

Write-Host "==> Checking pyproject.toml ..."
if (-not (Test-Path "pyproject.toml")) {
    Fail "pyproject.toml not found; run this script from the repository root."
}

Write-Host "==> uv sync --frozen ..."
uv sync --frozen
if ($LASTEXITCODE -ne 0) { Fail "uv sync failed" }

Write-Host "==> Lint (uv run ruff check src tests) ..."
uv run ruff check src tests
if ($LASTEXITCODE -ne 0) { Fail "ruff check failed; refusing to package" }

Write-Host "==> Tests (uv run pytest) ..."
uv run pytest
if ($LASTEXITCODE -ne 0) { Fail "tests failed; refusing to package" }

Write-Host "==> Removing old build / dist ..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "==> Running PyInstaller (one-folder) ..."
uv run pyinstaller --noconfirm paperlingo.spec
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed" }

$exe = "dist\PaperLingo\PaperLingo.exe"
if (-not (Test-Path $exe)) {
    Fail "expected executable not found: $exe"
}

Write-Host "==> Smoke launch of the packaged exe ..."
# A GUI app has no --help; start it, wait briefly, and stop it. Also verify the
# portable contract: the database must be created beside the exe, never bundled.
$dbInDist = "dist\PaperLingo\paperlingo.db"
if (Test-Path $dbInDist) { Remove-Item -Force $dbInDist, "$dbInDist-wal", "$dbInDist-shm" -ErrorAction SilentlyContinue }
$proc = Start-Process -FilePath (Resolve-Path $exe) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5
if ($proc.HasExited -and $proc.ExitCode -ne 0) {
    Fail "packaged exe exited immediately with code $($proc.ExitCode)"
}
if ($proc.HasExited) {
    Write-Host "packaged exe started and exited on its own (code $($proc.ExitCode))"
} else {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "packaged exe launched successfully (stopped the probe process)"
}
if (-not (Test-Path $dbInDist)) {
    Write-Host "note: paperlingo.db was not created during the short probe (it is created on first interactive run); checking that no dev DB was bundled:"
    Fail "portable contract violated? paperlingo.db missing beside the exe after launch"
} else {
    Write-Host "portable DB verified beside the exe: $dbInDist"
}

Write-Host ""
Write-Host "Build finished: $exe" -ForegroundColor Green
Write-Host "Ship the whole dist\PaperLingo\ directory - no Python / Qt / uv needed."
