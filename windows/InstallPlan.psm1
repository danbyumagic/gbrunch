# Pure planning functions. This module contains no disk-writing commands.
Set-StrictMode -Version Latest
$script:BasicData = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
$script:MinimumPartitionBytes = 48GB

function Get-TargetChoices {
    param([Parameter(Mandatory)]$Disk)
    $reasons = @()
    if ([string]::IsNullOrWhiteSpace($Disk.UniqueId)) { $reasons += 'Stable disk identity unavailable' }
    if ($Disk.PartitionStyle -ne 'GPT') { $reasons += 'Only existing GPT disks are supported' }
    if ($Disk.IsOffline -or $Disk.IsReadOnly) { $reasons += 'Disk is offline or read-only' }
    if ($Disk.Size -lt 64000000000) { $reasons += 'A drive of at least 64 GB is required' }
    if ($Disk.BusType -notin @('USB','NVMe','SATA','SAS')) { $reasons += 'Unsupported or ambiguous disk connection' }
    if ($Disk.HealthStatus -ne 'Healthy') { $reasons += 'Disk health is not confirmed healthy' }
    $parts = @($Disk.Partitions | Sort-Object Offset)
    $cursor = [long]1MB
    $end = [long]$Disk.Size - 1MB
    $layoutInvalid = $false
    foreach ($part in $parts) {
        if ($part.Offset -lt $cursor -or $part.Size -le 0 -or $part.Offset + $part.Size -gt $Disk.Size) { $layoutInvalid = $true }
        $cursor = [long]$part.Offset + [long]$part.Size
    }
    if ($layoutInvalid) { $reasons += 'Partition layout is inconsistent; refresh or inspect the disk' }
    $cursor = [long]1MB
    foreach ($part in $parts) {
        $aligned = [long]([Math]::Ceiling($cursor / 1MB) * 1MB)
        $gap = [long]([Math]::Floor(($part.Offset - $aligned) / 1MB) * 1MB)
        if ($gap -ge $script:MinimumPartitionBytes) {
            [pscustomobject]@{ Kind='Unallocated'; PartitionNumber=$null; Offset=$aligned; Size=$gap; Label='Unallocated space'; Eligible=($reasons.Count -eq 0); Reason=($reasons -join '; '); PartitionId=$null }
        }
        $blocked = @($reasons)
        if ($part.IsBoot -or $part.IsSystem -or $part.IsWindows) { $blocked += 'Windows or system partition is protected' }
        if ($part.GptType.Trim('{}').ToLowerInvariant() -ne $script:BasicData) { $blocked += 'EFI, recovery, reserved, OEM and unknown partition types are protected' }
        if ($part.Size -lt $script:MinimumPartitionBytes) { $blocked += 'Partition is smaller than 48 GiB' }
        if ($part.Encryption -ne 'FullyDecrypted') { $blocked += 'Encryption is enabled or unknown' }
        if ([string]::IsNullOrWhiteSpace($part.PartitionId)) { $blocked += 'Stable partition identity unavailable' }
        [pscustomobject]@{ Kind='ReplacePartition'; PartitionNumber=$part.Number; Offset=[long]$part.Offset; Size=[long]$part.Size; Label=$part.Label; Eligible=($blocked.Count -eq 0); Reason=($blocked -join '; '); PartitionId=$part.PartitionId }
        $cursor = [long]$part.Offset + [long]$part.Size
    }
    $aligned = [long]([Math]::Ceiling($cursor / 1MB) * 1MB)
    $gap = [long]([Math]::Floor(($end - $aligned) / 1MB) * 1MB)
    if ($gap -ge $script:MinimumPartitionBytes) {
        [pscustomobject]@{ Kind='Unallocated'; PartitionNumber=$null; Offset=$aligned; Size=$gap; Label='Unallocated space'; Eligible=($reasons.Count -eq 0); Reason=($reasons -join '; '); PartitionId=$null }
    }
}

function New-InstallPlan {
    param([Parameter(Mandatory)]$Disk, [Parameter(Mandatory)]$Choice)
    # Recompute policy from the inventory, never trust an enabled UI row alone.
    $matching = @(Get-TargetChoices $Disk | Where-Object { $_.Kind -eq $Choice.Kind -and $_.Offset -eq $Choice.Offset -and $_.Size -eq $Choice.Size -and $_.PartitionId -eq $Choice.PartitionId })
    if ($matching.Count -ne 1 -or -not $matching[0].Eligible) { throw 'Target is unavailable, protected or stale. Refresh the drive list.' }
    [pscustomobject][ordered]@{
        Schema='gbrunch-install-plan-v1'; CreatedUtc=[DateTime]::UtcNow.ToString('o')
        Status='PreviewOnly'; CanInstall=$false
        Blocker='Production image boot (including clean shutdown and UEFI) and the Windows deployment engine are not yet validated.'
        Disk=[pscustomobject]@{ Number=$Disk.Number; UniqueId=$Disk.UniqueId; Size=$Disk.Size; Model=$Disk.Model; BusType=$Disk.BusType; Connection=$(if ($Disk.BusType -eq 'USB') {'External USB'} else {'Internal/direct-attached; confirm physical drive'}) }
        Target=$matching[0]
        ErasesSelectedPartition=($Choice.Kind -eq 'ReplacePartition')
        Layout='One dedicated ext4 data partition containing a raw Googlebook image; separate EFI boot files required'
        EfiAction='Not planned yet; must select/validate an EFI System Partition before installation'
        Uninstall='Remove only installation-identified boot files and data partition; reclaiming space into Windows depends on adjacency'
        RecoveryProfile='profiles/ruby-16658739.json'
        Source='Download official recovery from Google and build privately; no Google image included'
    }
}

function Assert-PlanMatchesInventory {
    param([Parameter(Mandatory)]$Plan, [Parameter(Mandatory)]$Disk)
    if ($Plan.Disk.UniqueId -ne $Disk.UniqueId -or $Plan.Disk.Size -ne $Disk.Size -or $Plan.Disk.Number -ne $Disk.Number) { throw 'Disk identity changed. Select the target again.' }
    $null = New-InstallPlan $Disk $Plan.Target
    return $true
}
Export-ModuleMember -Function Get-TargetChoices,New-InstallPlan,Assert-PlanMatchesInventory
