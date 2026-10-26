# Destructive commands are MOCKED. No Windows disks are accessed by these tests.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Test-InstallPlan.ps1')
. (Join-Path $PSScriptRoot 'Prepare-Partition.ps1')
$script:testRoot=Join-Path ([IO.Path]::GetTempPath()) ('gbrunch-preparation-test-'+[Guid]::NewGuid())
$null=New-Item -ItemType Directory $script:testRoot
$script:admin=$true; $script:failFormat=$false; $script:protectNew=$false; $script:wrongGuid=$false
$script:calls=New-Object 'Collections.Generic.List[string]'
function Test-PreparationAdministrator { return $script:admin }
function Get-InstallInventory { return $script:disks }
function Get-Partition {
    [CmdletBinding()]param($DiskNumber,$PartitionNumber)
    $p=@($script:disks[0].Partitions | Where-Object Number -eq $PartitionNumber)[0]
    [pscustomobject]@{ Guid=$(if ($script:wrongGuid) {'changed'} else {$p.PartitionId}); Offset=$p.Offset; Size=$p.Size; IsBoot=$p.IsBoot; IsSystem=$p.IsSystem; PartitionNumber=$p.Number }
}
function New-Partition {
    [CmdletBinding()]param($DiskNumber,$Offset,$Size,$GptType,[switch]$AssignDriveLetter)
    $script:calls.Add('New-Partition')
    $p=Partition; $p.Offset=$Offset; $p.Size=$Size; $p.IsBoot=$script:protectNew; $p.Encryption='Unknown'; $script:disks[0].Partitions=@($p)
    Get-Partition -DiskNumber $DiskNumber -PartitionNumber $p.Number
}
function Format-Volume {
    [CmdletBinding(SupportsShouldProcess=$true)]param([Parameter(ValueFromPipeline)]$InputObject,$FileSystem,$NewFileSystemLabel)
    process {
        $script:calls.Add('Format-Volume')
        if ($script:failFormat) { throw 'Simulated formatting failure' }
        [pscustomobject]@{ FileSystem=$FileSystem; FileSystemLabel=$NewFileSystemLabel; HealthStatus='Healthy' }
    }
}
function New-TestLog { Join-Path $script:testRoot ([Guid]::NewGuid().ToString()) }
try {
    $script:disks=@(Disk); $plan=New-InstallPlan $script:disks[0] @(Get-TargetChoices $script:disks[0])[0]
    Reject { Invoke-StagingPreparation $plan 'wrong' (New-TestLog) } 'Incorrect confirmation rejects all writes'
    Assert ($script:calls.Count -eq 0) 'No writes after confirmation mismatch'
    $script:admin=$false
    Reject { Invoke-StagingPreparation $plan (Get-PreparationPhrase $plan) (New-TestLog) } 'Non-administrator blocked'
    $script:admin=$true
    $script:disks=@((Disk),(Disk))
    Reject { Invoke-StagingPreparation $plan (Get-PreparationPhrase $plan) (New-TestLog) } 'Duplicate disk identity blocked'
    Assert ($script:calls.Count -eq 0) 'No writes on failed validation'
    $script:disks=@(Disk)
    $log=New-TestLog
    $result=Invoke-StagingPreparation $plan (Get-PreparationPhrase $plan) $log
    Assert (($script:calls -join ',') -eq 'New-Partition,Format-Volume') 'Unallocated target creates then formats only the selected partition'
    Assert (-not $result.Bootable) 'Preparation never claims bootability'
    $j=Get-Content -Raw $result.Journal | ConvertFrom-Json
    Assert ($j.State -eq 'staging-prepared' -and $j.Result.FileSystem -eq 'NTFS') 'Successful preparation journal persisted'
    $script:disks=@(Disk); $script:disks[0].Partitions=@(Partition); $script:calls.Clear()
    $choice=@(Get-TargetChoices $script:disks[0] | Where-Object Kind -eq 'ReplacePartition')[0]
    $existing=New-InstallPlan $script:disks[0] $choice
    $null=Invoke-StagingPreparation $existing (Get-PreparationPhrase $existing) (New-TestLog)
    Assert (($script:calls -join ',') -eq 'Format-Volume') 'Existing partition formats in place without deleting or recreating'
    $script:calls.Clear(); $script:disks[0].Partitions[0].IsWindows=$true
    Reject { Invoke-StagingPreparation $existing (Get-PreparationPhrase $existing) (New-TestLog) } 'New Windows protection blocks an old plan'
    Assert ($script:calls.Count -eq 0) 'Protected target never formatted'
    $script:disks=@(Disk); $script:protectNew=$true
    Reject { Invoke-StagingPreparation $plan (Get-PreparationPhrase $plan) (New-TestLog) } 'New partition gaining protection is not formatted'
    Assert (($script:calls -join ',') -eq 'New-Partition') 'No format after post-create identity/protection failure'
    $script:protectNew=$false; $script:calls.Clear(); $script:disks=@(Disk); $script:failFormat=$true
    $log=New-TestLog
    Reject { Invoke-StagingPreparation $plan (Get-PreparationPhrase $plan) $log } 'Format errors stop preparation'
    $j=Get-Content -Raw (Join-Path $log 'preparation.json') | ConvertFrom-Json
    Assert ($j.State -eq 'failed-inspect-before-retrying' -and $j.PartitionId) 'Failure journal retains created partition identity'
    Assert ($script:disks[0].Partitions.Count -eq 1) 'No automatic deletion after failure'
    $script:failFormat=$false; $script:calls.Clear(); $script:disks=@(Disk); $script:disks[0].Partitions=@(Partition); $script:wrongGuid=$true
    Reject { Invoke-StagingPreparation $existing (Get-PreparationPhrase $existing) (New-TestLog) } 'Live CIM partition identity mismatch rejected'
    Assert ($script:calls.Count -eq 0) 'No format after CIM identity mismatch'
    Write-Host "$script:checks total checks passed. Disk mutation tests used mocks; no Windows format was executed."
} finally {
    Remove-Item -LiteralPath $script:testRoot -Recurse -Force
}
