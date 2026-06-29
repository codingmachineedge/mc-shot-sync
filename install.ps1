<#
.SYNOPSIS
  One-command installer for mc-shot-sync (Windows).

.EXAMPLE
  irm https://raw.githubusercontent.com/codingmachineedge/mc-shot-sync/main/install.ps1 | iex

.EXAMPLE
  # from a local checkout
  ./install.ps1

.NOTES
  Env overrides:
    MCSS_REPO    git URL to clone (default: this project's GitHub repo)
    MCSS_HOME    install dir       (default: %LOCALAPPDATA%\mc-shot-sync)
    MCSS_NOINIT  set to 1 to skip the interactive `init` step
#>
$ErrorActionPreference = "Stop"

function Say  ($m) { Write-Host "==> $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "!   $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "xx  $m" -ForegroundColor Red; exit 1 }

$RepoUrl = if ($env:MCSS_REPO) { $env:MCSS_REPO } else { "https://github.com/codingmachineedge/mc-shot-sync.git" }
$HomeDir = if ($env:MCSS_HOME) { $env:MCSS_HOME } else { Join-Path $env:LOCALAPPDATA "mc-shot-sync" }

# --- Locate source: local checkout or clone --------------------------------
$srcDir = $null
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { $null }
if ($scriptDir -and (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
    $srcDir = $scriptDir
    Say "Installing from local checkout: $srcDir"
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git is required. Install Git for Windows and retry." }
    $srcDir = Join-Path $HomeDir "src"
    if (Test-Path (Join-Path $srcDir ".git")) {
        Say "Updating existing checkout in $srcDir"
        git -C $srcDir pull --ff-only 2>$null
    } else {
        Say "Cloning $RepoUrl -> $srcDir"
        New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
        git clone --depth 1 $RepoUrl $srcDir
    }
}

# --- Python ----------------------------------------------------------------
$py = $null
foreach ($cand in @("py", "python", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) { Die "Python 3.9+ is required but was not found. Install from https://python.org" }
# `py` needs the -3 selector
$pyArgs = if ($py -eq "py") { @("-3") } else { @() }

$venv = Join-Path $HomeDir "venv"
Say "Creating virtualenv: $venv"
New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
& $py @pyArgs -m venv $venv
$venvPy = Join-Path $venv "Scripts\python.exe"
& $venvPy -m pip install --upgrade pip | Out-Null
Say "Installing mc-shot-sync and dependencies"
& $venvPy -m pip install $srcDir

# --- Launcher shim on PATH -------------------------------------------------
$binDir = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"  # already on PATH
if (-not (Test-Path $binDir)) { $binDir = Join-Path $HomeDir "bin" }
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$exeTarget = Join-Path $venv "Scripts\mc-shot-sync.exe"
$cmdShim = Join-Path $binDir "mc-shot-sync.cmd"
"@echo off`r`n`"$exeTarget`" %*" | Set-Content -Path $cmdShim -Encoding ASCII
Say "Installed launcher: $cmdShim"

# Ensure the chosen bin dir is on the user PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    Warn "Added $binDir to your user PATH. Open a new terminal for it to take effect."
}

# --- First-run setup -------------------------------------------------------
if ($env:MCSS_NOINIT -ne "1") {
    Say "Running setup (detect screenshots, create the public GitHub repo)..."
    & $exeTarget init
    if ($LASTEXITCODE -ne 0) { Warn "init did not finish — re-run 'mc-shot-sync init' after fixing the issue above." }
}

Say "Done!"
Write-Host "Start the tray GUI:   mc-shot-sync tray"
Write-Host "Or run headless:      mc-shot-sync watch"
Write-Host "Check configuration:  mc-shot-sync status"
