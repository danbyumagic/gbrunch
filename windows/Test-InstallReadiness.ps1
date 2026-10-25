# Read-only inventory for a future Windows installer. This does not install,
# shrink/format disks, edit BCD/EFI, change BitLocker, or install WSL.
[CmdletBinding()]
param([string]$OutputDirectory = (Join-Path (Get-Location) 'gbrunch-readiness'))
$ErrorActionPreference = 'Stop'
$results = [ordered]@{
    schema = 'gbrunch-windows-readiness-v1'
    scope = 'Read-only inventory; not installation approval or a compatibility guarantee'
    architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    collectedUtc = [DateTime]::UtcNow.ToString('o')
    checks = [ordered]@{}
}
function Read-Check([string]$Name, [scriptblock]$Operation) {
    try { $results.checks[$Name] = @{ ok = $true; value = @(& $Operation) } }
    catch { $results.checks[$Name] = @{ ok = $false; error = $_.Exception.Message } }
}
Read-Check 'disks' { Get-Disk | Select-Object Number, FriendlyName, BusType, PartitionStyle, Size, IsBoot, IsSystem, IsOffline, IsReadOnly }
Read-Check 'partitions' { Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Type, Size, Offset, IsBoot, IsSystem }
Read-Check 'volumes' { Get-Volume | Select-Object DriveLetter, FileSystemType, Size, SizeRemaining, HealthStatus }
Read-Check 'firmware' { Get-ComputerInfo -Property BiosFirmwareType | Select-Object BiosFirmwareType }
Read-Check 'secureBoot' { Confirm-SecureBootUEFI }
Read-Check 'cpuVirtualization' { Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled, SecondLevelAddressTranslationExtensions }
Read-Check 'bitLocker' {
    if (-not (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue)) { throw 'BitLocker status command unavailable; status unknown' }
    Get-BitLockerVolume | Select-Object MountPoint, VolumeType, VolumeStatus, ProtectionStatus, EncryptionPercentage
}
Read-Check 'wsl' {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'WSL command is not installed' }
    $text = & wsl.exe --list --verbose 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($text -join "`n") }
    $text
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$path = Join-Path $OutputDirectory 'readiness.json'
if (Test-Path $path) { throw "Report already exists: $path. Use another output directory." }
$results | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $path
Write-Host "Read-only report saved to $path"
Write-Host 'No disk, boot configuration, encryption setting or WSL distribution was changed.'
Write-Host 'Inspect the report before sharing. This is not an installer.'
