@echo off
powershell.exe -NoProfile -STA -File "%~dp0Start-Installer.ps1"
if errorlevel 1 pause
