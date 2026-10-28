# Build a private Googlebook image through the existing WSL distribution.
# This script never accesses a Windows physical drive.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run on Windows with an existing Ubuntu WSL distribution.' }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'This build workflow requires x86-64 Windows.' }
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'WSL is unavailable. This workflow does not install Linux.' }
$repo=Split-Path -Parent $PSScriptRoot
Write-Host 'Building the traditional HP external-drive layout, not the one-partition experiment.'
Write-Host 'The official recovery is downloaded from Google and built locally. No SSD is written.'
Write-Host 'Uses your existing default WSL distribution; it should be Ubuntu x86-64.'
& wsl.exe --cd $repo --exec bash tools/build_hp_external_wsl.sh
if ($LASTEXITCODE -ne 0) { throw 'Build did not finish. Read the error above; do not flash an incomplete image.' }
Write-Host 'Build finished. The image path and checksum are printed above. Keep this image private.'
