# Explicitly destructive NTFS staging preparation, separate from OS installation.
# Dot-source after InstallPlan.psm1 and Get-InstallInventory.ps1.
Set-StrictMode -Version Latest
function Test-PreparationAdministrator {
    if ($env:OS -ne 'Windows_NT') { return $false }
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal $identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Get-PreparationPhrase($Plan) {
    if ($Plan.Target.Kind -eq 'ReplacePartition') { return "ERASE DISK $($Plan.Disk.Number) PARTITION $($Plan.Target.PartitionNumber)" }
    return "PREPARE DISK $($Plan.Disk.Number)"
}
function Get-PreparationDisk($Plan) {
    $all=@(Get-InstallInventory)
    $matches=@($all | Where-Object { $_.UniqueId -eq $Plan.Disk.UniqueId })
    if ($matches.Count -ne 1) { throw 'Missing or duplicate disk identity. Refresh and select the target again.' }
    if ($matches[0].Number -ne $Plan.Disk.Number -or $matches[0].Size -ne $Plan.Disk.Size) { throw 'Disk changed since selection.' }
    return $matches[0]
}
function Invoke-StagingPreparation {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Plan, [Parameter(Mandatory)][string]$Confirmation,
          [Parameter(Mandatory)][string]$LogDirectory)
    if (-not (Test-PreparationAdministrator)) { throw 'Open Windows PowerShell as administrator to prepare a partition.' }
    if ($Plan.Schema -ne 'gbrunch-install-plan-v1') { throw 'Unknown plan schema.' }
    if ($Confirmation -cne (Get-PreparationPhrase $Plan)) { throw 'Erase confirmation does not match the selected target.' }
    $disk=Get-PreparationDisk $Plan
    $null=Assert-PlanMatchesInventory $Plan $disk
    # Journaling must work before any write. No automatic partition deletion on error.
    $null=New-Item -ItemType Directory -Path $LogDirectory -ErrorAction Stop
    $journalPath=Join-Path $LogDirectory 'preparation.json'
    $journal=[ordered]@{ Schema='gbrunch-staging-preparation-v1'; StartedUtc=[DateTime]::UtcNow.ToString('o'); Plan=$Plan; State='validated'; PartitionId=$null; Result=$null; Error=$null }
    function Save-Journal { $journal | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $journalPath -Encoding UTF8 -ErrorAction Stop }
    Save-Journal
    try {
        # Re-read after journal creation, immediately before the first mutation.
        $disk=Get-PreparationDisk $Plan
        $null=Assert-PlanMatchesInventory $Plan $disk
        if ($Plan.Target.Kind -eq 'Unallocated') {
            $journal.State='creating-partition'; Save-Journal
            $part=New-Partition -DiskNumber $disk.Number -Offset $Plan.Target.Offset -Size $Plan.Target.Size -GptType '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}' -AssignDriveLetter -ErrorAction Stop
            $journal.PartitionId=[string]$part.Guid
            $journal.State='partition-created'; Save-Journal
        } else {
            $part=Get-Partition -DiskNumber $disk.Number -PartitionNumber $Plan.Target.PartitionNumber -ErrorAction Stop
            if ([string]$part.Guid -ne $Plan.Target.PartitionId) { throw 'Partition identity changed before formatting.' }
            $journal.PartitionId=[string]$part.Guid
        }
        if ([string]::IsNullOrWhiteSpace([string]$part.Guid)) { throw 'Prepared partition has no stable identity.' }
        $disk=Get-PreparationDisk $Plan
        $actual=@($disk.Partitions | Where-Object { $_.PartitionId -eq [string]$part.Guid })
        if ($actual.Count -ne 1) { throw 'Prepared partition disappeared or identity is ambiguous.' }
        $target=$actual[0]
        if ($disk.PartitionStyle -ne 'GPT' -or $disk.IsOffline -or $disk.IsReadOnly -or $disk.HealthStatus -ne 'Healthy' -or $disk.BusType -notin @('USB','NVMe','SATA','SAS')) { throw 'Disk state changed before formatting.' }
        if ($target.Offset -ne $Plan.Target.Offset -or $target.Size -ne $Plan.Target.Size -or $target.IsBoot -or $target.IsSystem -or $target.IsWindows -or $target.GptType.Trim('{}').ToLowerInvariant() -ne 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7') { throw 'Target geometry or protection changed before formatting.' }
        if ($Plan.Target.Kind -eq 'ReplacePartition') { $null=Assert-PlanMatchesInventory $Plan $disk }
        # Use the freshly identified CIM partition object; never target a drive letter.
        $part=Get-Partition -DiskNumber $disk.Number -PartitionNumber $target.Number -ErrorAction Stop
        if ([string]$part.Guid -ne $journal.PartitionId -or $part.Offset -ne $target.Offset -or $part.Size -ne $target.Size -or $part.IsBoot -or $part.IsSystem) { throw 'Partition changed immediately before formatting.' }
        $journal.State='formatting-ntfs'; Save-Journal
        $volume=$part | Format-Volume -FileSystem NTFS -NewFileSystemLabel 'GBRUNCH_STAGE' -Confirm:$false -ErrorAction Stop
        if ([string]$volume.FileSystem -ne 'NTFS' -or [string]$volume.FileSystemLabel -ne 'GBRUNCH_STAGE' -or [string]$volume.HealthStatus -ne 'Healthy') { throw 'NTFS format result did not match expectations.' }
        $journal.Result=[ordered]@{ FileSystem='NTFS'; Label='GBRUNCH_STAGE'; PartitionId=$journal.PartitionId; Bootable=$false; Purpose='Temporary staging only; final ext4 deployment replaces this filesystem and its files.' }
        $journal.State='staging-prepared'; Save-Journal
        return [pscustomobject]@{ Journal=$journalPath; PartitionId=$journal.PartitionId; Bootable=$false }
    } catch {
        $journal.Error=$_.Exception.Message
        $journal.State='failed-inspect-before-retrying'
        try { Save-Journal } catch { }
        throw "Preparation stopped: $($journal.Error). Inspect $journalPath. A new partition may remain; nothing is automatically deleted."
    }
}
