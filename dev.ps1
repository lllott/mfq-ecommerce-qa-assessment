#Requires -Version 5.1
<#
    一条命令启动本地开发环境：
      1. 检查 Python / Node / npm
      2. 准备后端虚拟环境并安装依赖
      3. 安装前端依赖、按需复制 .env
      4. 启动 FastAPI，等健康检查通过后再启动 Vite
      5. Ctrl+C 时一起收掉两个进程

    用法：
      .\dev.ps1
      .\dev.ps1 -SkipInstall          # 依赖已装好，跳过安装
      .\dev.ps1 -BackendPort 8010 -FrontendPort 5180
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'app\backend'
$frontendDir = Join-Path $root 'app\frontend'

function Stop-WithError([string]$Message) {
    Write-Host ""
    Write-Host "[✗] $Message" -ForegroundColor Red
    exit 1
}

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "[·] $Message" -ForegroundColor Cyan
}

# ------------------------------------------------------------------ 1. 工具链
Write-Step '检查运行环境'

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Stop-WithError '找不到 Python。请先安装 Python 3.11+（https://www.python.org/downloads/）。'
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Stop-WithError '找不到 Node.js。请先安装 Node.js 18+（https://nodejs.org/）。'
}

# Windows 上 npm.ps1 常被执行策略拦住，优先用 npm.cmd。
$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
}
if (-not $npmCmd) {
    Stop-WithError '找不到 npm（应随 Node.js 一起安装）。'
}

Write-Host "    Python : $($pythonCmd.Source)"
Write-Host "    Node   : $((Get-Command node).Source)"
Write-Host "    npm    : $($npmCmd.Source)"

if (-not (Test-Path $backendDir)) { Stop-WithError "找不到后端目录：$backendDir" }
if (-not (Test-Path $frontendDir)) { Stop-WithError "找不到前端目录：$frontendDir" }

# ------------------------------------------------------------------ 2. 后端
$venvDir = Join-Path $backendDir '.venv'

# Windows 的解释器在 Scripts\ 下，类 Unix 在 bin/ 下，用这个函数统一取路径。
function Get-VenvPython([string]$VenvDir) {
    $win = Join-Path $VenvDir 'Scripts\python.exe'
    if (Test-Path $win) { return $win }
    $unix = Join-Path $VenvDir 'bin/python'
    if (Test-Path $unix) { return $unix }
    return $null
}

$venvPython = Get-VenvPython $venvDir

if (-not $venvPython) {
    Write-Step '创建后端虚拟环境 .venv'
    & $pythonCmd.Source -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Stop-WithError '创建虚拟环境失败。' }

    # 创建之后必须重新解析，否则会拿到 Windows 上并不存在的 bin/python。
    $venvPython = Get-VenvPython $venvDir
    if (-not $venvPython) { Stop-WithError '虚拟环境创建后仍找不到 python 解释器。' }
}

if (-not $SkipInstall) {
    Write-Step '安装后端依赖'
    & $venvPython -m pip install --quiet --disable-pip-version-check --timeout 30 --retries 2 -r (Join-Path $backendDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { Stop-WithError '后端依赖安装失败，请检查网络或 pip 源。' }
}

# ------------------------------------------------------------------ 3. 前端
if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    if ($SkipInstall) {
        Stop-WithError '尚未安装前端依赖，请去掉 -SkipInstall 后再运行一次。'
    }
    Write-Step '安装前端依赖（首次较慢）'
    Push-Location $frontendDir
    try {
        & $npmCmd.Source install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Stop-WithError '前端依赖安装失败。' }
    }
    finally {
        Pop-Location
    }
}

$envFile = Join-Path $frontendDir '.env'
if (-not (Test-Path $envFile) -and (Test-Path (Join-Path $frontendDir '.env.example'))) {
    Copy-Item (Join-Path $frontendDir '.env.example') $envFile
    Write-Host "    已从 .env.example 生成 .env"
}

# ------------------------------------------------------------------ 4. 启动
$backendJob = $null
try {
    Write-Step "启动后端 http://127.0.0.1:$BackendPort"
    $backendJob = Start-Job -ScriptBlock {
        param($Python, $WorkDir, $Port)
        Set-Location $WorkDir
        & $Python -m uvicorn main:app --host 127.0.0.1 --port $Port
    } -ArgumentList $venvPython, $backendDir, $BackendPort

    $healthUrl = "http://127.0.0.1:$BackendPort/api/products/tee-001"
    $deadline = (Get-Date).AddSeconds(45)
    $healthy = $false
    while (-not $healthy -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if ($backendJob.State -eq 'Failed') { break }
        try {
            $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $healthUrl
            $healthy = $true
        }
        catch {
            # 后端还没起来，继续等
        }
    }

    if (-not $healthy) {
        Write-Host ''
        Write-Host '--- 后端输出 ---' -ForegroundColor Yellow
        Receive-Job $backendJob -Keep | Select-Object -Last 30 | ForEach-Object { Write-Host $_ }
        Stop-WithError "后端未能在 45 秒内响应 $healthUrl（端口 $BackendPort 可能被占用）。"
    }
    Write-Host "    [✓] 后端就绪" -ForegroundColor Green

    Write-Step "启动前端 http://127.0.0.1:$FrontendPort"
    Write-Host ""
    Write-Host "    后端 API : http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
    Write-Host "    商品详情 : http://127.0.0.1:$FrontendPort" -ForegroundColor Green
    Write-Host "    按 Ctrl+C 结束" -ForegroundColor DarkGray
    Write-Host ""

    Push-Location $frontendDir
    try {
        # 把本次实际的后端端口传给 Vite，避免 .env 里写死的地址和 -BackendPort 不一致。
        $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
        & $npmCmd.Source run dev -- --port $FrontendPort --strictPort
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($backendJob) {
        Write-Host ''
        Write-Host '[·] 正在结束后端进程…' -ForegroundColor Cyan
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
    }
}
