# Portable policy tests: pwsh -NoProfile -File windows/Test-InstallPlan.ps1
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'InstallPlan.psm1') -Force
$script:checks=0
function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    $script:checks++
}
function Reject([scriptblock]$Operation, [string]$Message) {
    $failed=$false
    try { $null=& $Operation } catch { $failed=$true }
    Assert $failed $Message
}
function Disk {
    [pscustomobject]@{ Number=3; UniqueId='test-usb-identity'; Model='Fixture USB'; Size=[long]240000000000; BusType='USB'; PartitionStyle='GPT'; IsOffline=$false; IsReadOnly=$false; HealthStatus='Healthy'; Partitions=@() }
}
function Partition {
    [pscustomobject]@{ Number=1; PartitionId='fixture-partition-guid'; Offset=[long]1MB; Size=[long]80GB; GptType='ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'; IsBoot=$false; IsSystem=$false; IsWindows=$false; Encryption='FullyDecrypted'; Label='Fixture files' }
}
$disk=Disk
$choice=@(Get-TargetChoices $disk)[0]
Assert ($choice.Eligible -and $choice.Kind -eq 'Unallocated') 'Empty USB GPT has an eligible unallocated extent'
$plan=New-InstallPlan $disk $choice
Assert (-not $plan.CanInstall -and $plan.Status -eq 'PreviewOnly') 'No plan can authorize writes'
Assert (-not $plan.ErasesSelectedPartition) 'Unallocated choice does not describe existing-partition erasure'
Assert ($plan.Disk.Connection -eq 'External USB') 'USB SSD is explicitly identified'
Assert (Assert-PlanMatchesInventory $plan $disk) 'Unchanged inventory revalidates'
$disk.Number=4
Reject { Assert-PlanMatchesInventory $plan $disk } 'Reconnected drive number requires reselection'
$disk=Disk; $disk.UniqueId='replacement'
Reject { Assert-PlanMatchesInventory $plan $disk } 'Replacement drive rejected'
$disk=Disk; $disk.Partitions=@(Partition)
$choice=@(Get-TargetChoices $disk | Where-Object Kind -eq 'ReplacePartition')[0]
Assert $choice.Eligible 'Decrypted non-system data partition eligible for preview'
Assert ((New-InstallPlan $disk $choice).ErasesSelectedPartition) 'Existing target explicitly warns of erasure'
$disk.Partitions[0].Offset+=1MB
Reject { New-InstallPlan $disk $choice } 'Stale partition geometry rejected'
foreach ($flag in @('IsBoot','IsSystem','IsWindows')) {
    $disk=Disk; $part=Partition; $part.$flag=$true; $disk.Partitions=@($part)
    $choice=@(Get-TargetChoices $disk | Where-Object Kind -eq 'ReplacePartition')[0]
    Assert (-not $choice.Eligible) "$flag protected"
    $choice.Eligible=$true
    Reject { New-InstallPlan $disk $choice } 'Forged enabled UI row does not override policy'
}
foreach ($type in @('c12a7328-f81f-11d2-ba4b-00a0c93ec93b','de94bba4-06d1-4d40-a16a-bfd50179d6ac','e3c9e316-0b5c-4db8-817d-f92df00215ae','unknown')) {
    $disk=Disk; $part=Partition; $part.GptType=$type; $disk.Partitions=@($part)
    Assert (-not @(Get-TargetChoices $disk | Where-Object Kind -eq 'ReplacePartition')[0].Eligible) 'EFI/recovery/reserved/unknown type protected'
}
foreach ($state in @('Unknown','Encrypted')) {
    $disk=Disk; $part=Partition; $part.Encryption=$state; $disk.Partitions=@($part)
    Assert (-not @(Get-TargetChoices $disk | Where-Object Kind -eq 'ReplacePartition')[0].Eligible) 'Encrypted or unknown partition blocked'
}
foreach ($bus in @('NVMe','SATA')) {
    $disk=Disk; $disk.BusType=$bus; $part=Partition; $part.IsWindows=$true; $disk.Partitions=@($part)
    Assert (@(Get-TargetChoices $disk | Where-Object Kind -eq 'Unallocated')[0].Eligible) 'Internal disk can use unallocated space while Windows stays protected'
}
foreach ($property in @('IsReadOnly','IsOffline')) {
    $disk=Disk; $disk.$property=$true
    Assert (-not @(Get-TargetChoices $disk)[0].Eligible) "$property disk blocked"
}
$disk=Disk; $disk.PartitionStyle='MBR'
Assert (-not @(Get-TargetChoices $disk)[0].Eligible) 'No implicit GPT conversion'
$disk=Disk; $disk.Size=[long]64000000000
Assert (@(Get-TargetChoices $disk)[0].Eligible) 'A nominal 64 GB GPT drive can hold the proposed partition'
$disk=Disk; $disk.Size=[long]32000000000
Assert (@(Get-TargetChoices $disk).Count -eq 0) 'Small drive has no install extent'
$disk=Disk; $a=Partition; $b=Partition; $b.Number=2; $b.PartitionId='second'; $disk.Partitions=@($a,$b)
Assert (@(Get-TargetChoices $disk | Where-Object Eligible).Count -eq 0) 'Overlapping layout blocked'
$disk=Disk; $disk.UniqueId=''
Assert (-not @(Get-TargetChoices $disk)[0].Eligible) 'Missing stable identity blocked'
$disk=Disk; $plan=New-InstallPlan $disk @(Get-TargetChoices $disk)[0]
$part=Partition; $disk.Partitions=@($part)
Reject { Assert-PlanMatchesInventory $plan $disk } 'Newly occupied free extent invalidates old plan'

# Parse all Windows entry points without executing Windows-only commands or WPF.
foreach ($path in @(Get-ChildItem $PSScriptRoot -Filter '*.ps*1')) {
    $tokens=$null; $errors=$null
    $null=[Management.Automation.Language.Parser]::ParseFile($path.FullName,[ref]$tokens,[ref]$errors)
    Assert ($errors.Count -eq 0) "PowerShell syntax: $($path.Name)"
}
$source=Get-Content -Raw (Join-Path $PSScriptRoot 'Start-Installer.ps1')
$match=[regex]::Match($source,"(?s)\[xml\]\`$xaml = @'\r?\n(.*?)\r?\n'@")
Assert $match.Success 'WPF layout found'
$null=[xml]$match.Groups[1].Value
Assert $true 'WPF layout XML parses'
Write-Host "$script:checks checks passed; Windows Storage and WPF runtime still require Windows testing."
