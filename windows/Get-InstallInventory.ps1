# Windows Storage inventory only; errors stop enumeration rather than imply safety.
Set-StrictMode -Version Latest
function Get-InstallInventory {
    $systemLetter = $env:SystemDrive.TrimEnd(':')
    foreach ($disk in @(Get-Disk -ErrorAction Stop)) {
        $parts = foreach ($part in @(Get-Partition -DiskNumber $disk.Number -ErrorAction Stop)) {
            $volume = $null
            try { $volume = $part | Get-Volume -ErrorAction Stop } catch { }
            $encryption = 'Unknown'
            if ($part.DriveLetter -and (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue)) {
                try {
                    $bl = Get-BitLockerVolume -MountPoint "$($part.DriveLetter):" -ErrorAction Stop
                    if ([string]$bl.VolumeStatus -eq 'FullyDecrypted' -and [string]$bl.ProtectionStatus -eq 'Off') { $encryption = 'FullyDecrypted' }
                } catch { }
            }
            $label = "Partition $($part.PartitionNumber)"
            if ($volume) { $label += " $($volume.FileSystemLabel) [$($volume.FileSystem)]" }
            if ($part.DriveLetter) { $label += " $($part.DriveLetter):" }
            [pscustomobject]@{
                Number=$part.PartitionNumber; PartitionId=[string]$part.Guid
                Offset=[long]$part.Offset; Size=[long]$part.Size; GptType=[string]$part.GptType
                IsBoot=[bool]$part.IsBoot; IsSystem=[bool]$part.IsSystem
                IsWindows=([string]$part.DriveLetter -eq $systemLetter)
                Encryption=$encryption; Label=$label
            }
        }
        [pscustomobject]@{
            Number=$disk.Number; UniqueId=[string]$disk.UniqueId; Model=[string]$disk.FriendlyName
            Size=[long]$disk.Size; BusType=[string]$disk.BusType; PartitionStyle=[string]$disk.PartitionStyle
            IsOffline=[bool]$disk.IsOffline; IsReadOnly=[bool]$disk.IsReadOnly
            HealthStatus=[string]$disk.HealthStatus; Partitions=@($parts)
        }
    }
}
