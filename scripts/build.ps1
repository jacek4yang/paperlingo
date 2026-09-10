# PaperLingo Windows 构建脚本
# 使用 uv 管理整个流程：检查 → sync → 测试 → 清理 → PyInstaller → 验证 exe
# 用法（PowerShell）：
#   .\scripts\build.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Fail([string]$msg) {
    Write-Host $msg -ForegroundColor Red
    exit 1
}

Write-Host "==> 检查 uv ..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "未找到 uv，请先安装 uv。"
}
uv --version

Write-Host "==> 检查 pyproject.toml ..."
if (-not (Test-Path "pyproject.toml")) {
    Fail "当前目录没有 pyproject.toml，请在项目根目录运行。"
}

Write-Host "==> uv sync ..."
uv sync
if ($LASTEXITCODE -ne 0) { Fail "uv sync 失败" }

Write-Host "==> 运行测试 (uv run pytest) ..."
uv run pytest
if ($LASTEXITCODE -ne 0) { Fail "测试未通过，停止打包" }

Write-Host "==> 运行 Lint (uv run ruff check src tests) ..."
uv run ruff check src tests
if ($LASTEXITCODE -ne 0) { Fail "ruff 检查未通过，停止打包" }

Write-Host "==> 清理旧的 build / dist ..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "==> PyInstaller 打包 ..."
uv run pyinstaller --noconfirm paperlingo.spec
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller 失败" }

$exe = "dist\PaperLingo\PaperLingo.exe"
if (-not (Test-Path $exe)) {
    Fail "未找到 $exe"
}

Write-Host "==> 验证 exe 能启动 ..."
# 启动后立刻用 --help 风格探测：窗口应用无法 --help，改为短超时启动后结束
$proc = Start-Process -FilePath (Resolve-Path $exe) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 4
if ($proc.HasExited -and $proc.ExitCode -ne 0) {
    Fail "exe 启动后立刻异常退出，退出码 $($proc.ExitCode)"
}
if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "exe 已成功启动（已结束探测进程）"
} else {
    Write-Host "exe 已启动并自行退出（退出码 $($proc.ExitCode)）"
}

Write-Host ""
Write-Host "构建完成: $exe" -ForegroundColor Green
Write-Host "把 dist\PaperLingo\ 整个目录拷给用户即可运行，无需安装 Python / Qt / uv。"
