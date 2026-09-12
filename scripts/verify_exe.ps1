# GmailAI Assistant - Executable Build & Smoke Test Verification Script
# Usage: powershell -ExecutionPolicy Bypass -File scripts\verify_exe.ps1

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " GmailAI Assistant - Windows Executable Verification" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 1. Check Python and PyInstaller
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$PyInstallerExe = Join-Path $ProjectRoot "venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $PyInstallerExe)) {
    Write-Error "PyInstaller not found at $PyInstallerExe. Run 'pip install -r requirements-dev.txt'."
    exit 1
}

Write-Host "`n[1/4] Validating PyInstaller and Python environment..." -ForegroundColor Yellow
& $PythonExe --version
& $PyInstallerExe --version

# 2. Build Executable
Write-Host "`n[2/4] Building Windows Executable via installer\gmailai.spec..." -ForegroundColor Yellow
$SpecPath = Join-Path $ProjectRoot "installer\gmailai.spec"

& $PyInstallerExe --clean --noconfirm --distpath (Join-Path $ProjectRoot "dist") --workpath (Join-Path $ProjectRoot "build") $SpecPath

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed with exit code $LASTEXITCODE."
    exit 1
}

$ExePath = Join-Path $ProjectRoot "dist\GmailAI Assistant\GmailAI Assistant.exe"
if (-not (Test-Path $ExePath)) {
    # Check one-file location
    $ExePath = Join-Path $ProjectRoot "dist\GmailAI Assistant.exe"
}

if (-not (Test-Path $ExePath)) {
    Write-Error "Build completed but target executable not found in dist/."
    exit 1
}

$ExeSize = (Get-Item $ExePath).Length / 1MB
Write-Host "Executable generated successfully: $ExePath ($([math]::Round($ExeSize, 2)) MB)" -ForegroundColor Green

# 3. Launch Smoke Test in clean sub-environment
Write-Host "`n[3/4] Launching smoke test process..." -ForegroundColor Yellow

$SmokeEnv = [System.Collections.Hashtable]::new()
$SmokeEnv["GMAILAI_DEMO_MODE"] = "true"

$ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
$ProcessInfo.FileName = $ExePath
$ProcessInfo.EnvironmentVariables["GMAILAI_DEMO_MODE"] = "true"
$ProcessInfo.UseShellExecute = $false
$ProcessInfo.CreateNoWindow = $false

$Process = [System.Diagnostics.Process]::Start($ProcessInfo)
if ($null -eq $Process) {
    Write-Error "Failed to start executable process."
    exit 1
}

Write-Host "Process started with PID: $($Process.Id). Monitoring for 5 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 5

if ($Process.HasExited) {
    $Code = $Process.ExitCode
    if ($Code -ne 0) {
        Write-Error "Process exited prematurely with error code $Code."
        exit 1
    }
} else {
    Write-Host "Process is running smoothly without crash. Terminating smoke test process..." -ForegroundColor Green
    $Process.Kill()
    $Process.WaitForExit(3000)
}

# 4. Summary
Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host " VERIFICATION RESULT: PASS" -ForegroundColor Green
Write-Host " Executable: $ExePath" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor Cyan
exit 0
