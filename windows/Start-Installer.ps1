# Windows PowerShell 5.1 / WPF front end. NTFS staging; OS installation unavailable.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run this interface on Windows.' }
if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') { throw 'Start with powershell.exe -STA -File windows\Start-Installer.ps1' }
Import-Module (Join-Path $PSScriptRoot 'InstallPlan.psm1') -Force
. (Join-Path $PSScriptRoot 'Get-InstallInventory.ps1')
. (Join-Path $PSScriptRoot 'Prepare-Partition.ps1')
Add-Type -AssemblyName PresentationFramework
[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="GBRUNCH - experimental partition preparation" Width="1000" Height="760" MinWidth="800" MinHeight="650" WindowStartupLocation="CenterScreen">
 <Grid Margin="20"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="180"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
 <TextBlock Text="Experimental Windows builder and partition preparation" FontSize="23" FontWeight="Bold" TextWrapping="Wrap"/>
 <TextBlock Grid.Row="1" Margin="0,12" TextWrapping="Wrap" Text="Build HP external OS creates a traditional disk-image file through existing Ubuntu WSL; flash it separately. NTFS preparation is not needed for that image and can ERASE the selected partition. Single-partition OS installation remains disabled."/>
 <DockPanel Grid.Row="2" Margin="0,0,0,10"><Button Name="BuildHP" DockPanel.Dock="Right" Content="Build HP external OS..." Padding="12,6" Margin="8,0,0,0"/><Button Name="Refresh" DockPanel.Dock="Right" Content="Refresh drives" Padding="12,6"/><ComboBox Name="Drives" DisplayMemberPath="Display" Margin="0,0,10,0"/></DockPanel>
 <DataGrid Name="Targets" Grid.Row="3" IsReadOnly="True" AutoGenerateColumns="False" SelectionMode="Single" SelectionUnit="FullRow" CanUserAddRows="False">
 <DataGrid.Columns><DataGridTextColumn Header="Target" Binding="{Binding Label}" Width="2*"/><DataGridTextColumn Header="Size (GiB)" Binding="{Binding GiB}" Width="90"/><DataGridCheckBoxColumn Header="Eligible" Binding="{Binding Eligible}" Width="70"/><DataGridTextColumn Header="Protection / reason" Binding="{Binding Reason}" Width="3*"/></DataGrid.Columns></DataGrid>
 <TextBox Name="Preview" Grid.Row="4" Margin="0,12" IsReadOnly="True" TextWrapping="Wrap" VerticalScrollBarVisibility="Auto" Text="Select a drive, then a partition or unallocated extent. No target is selected automatically."/>
 <StackPanel Grid.Row="5" Orientation="Horizontal" HorizontalAlignment="Right"><Button Name="Save" Content="Save plan..." IsEnabled="False" Padding="14,8" Margin="0,0,12,0"/><Button Name="Prepare" Content="Prepare staging (NTFS)..." IsEnabled="False" Padding="14,8" Margin="0,0,12,0"/><Button Content="Install - not yet available" IsEnabled="False" Padding="14,8"/></StackPanel>
 </Grid>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load((New-Object Xml.XmlNodeReader $xaml))
$drives=$window.FindName('Drives'); $targets=$window.FindName('Targets'); $preview=$window.FindName('Preview'); $save=$window.FindName('Save')
$prepare=$window.FindName('Prepare')
$script:plan = $null
function Show-Error($err) { $preview.Text = "Unable to continue: $err"; $save.IsEnabled=$false; $prepare.IsEnabled=$false; $script:plan=$null }
function Refresh-Drives {
    $save.IsEnabled=$false; $prepare.IsEnabled=$false; $script:plan=$null; $targets.ItemsSource=$null; $drives.ItemsSource=$null
    try {
        $script:inventory=@(Get-InstallInventory)
        $rows=@($script:inventory | ForEach-Object { [pscustomobject]@{ Display="Disk $($_.Number) | $($_.Model) | $([Math]::Round($_.Size / 1GB,1)) GiB | $($_.BusType) | $($_.PartitionStyle)"; Disk=$_ } })
        $drives.ItemsSource=$rows; $drives.SelectedIndex=-1
        $preview.Text='Choose a drive by model, size and connection. Disk numbers can change after reconnecting. C: free space is not unallocated space; this preview never shrinks Windows.'
    } catch { Show-Error $_.Exception.Message }
}
$drives.Add_SelectionChanged({
    $save.IsEnabled=$false; $prepare.IsEnabled=$false; $script:plan=$null; $targets.ItemsSource=$null
    if ($drives.SelectedItem) {
        try { $targets.ItemsSource=@(Get-TargetChoices $drives.SelectedItem.Disk | ForEach-Object { $_ | Add-Member -NotePropertyName GiB -NotePropertyValue ([Math]::Round($_.Size / 1GB,2)) -PassThru }); $targets.SelectedIndex=-1; $preview.Text='Choose a target. Replacing a partition erases all files in that partition. Protected rows cannot be used.' } catch { Show-Error $_.Exception.Message }
    }
})
$targets.Add_SelectionChanged({
    $save.IsEnabled=$false; $prepare.IsEnabled=$false; $script:plan=$null
    if ($targets.SelectedItem -and $drives.SelectedItem) {
        try {
            $script:plan=New-InstallPlan $drives.SelectedItem.Disk $targets.SelectedItem
            $warning=if ($script:plan.ErasesSelectedPartition) {'WOULD ERASE the selected partition and every file in it.'} else {'Would create one partition inside the selected unallocated extent.'}
            $preview.Text="$warning`r`n`r`n" + ($script:plan | ConvertTo-Json -Depth 8)
            $save.IsEnabled=$true
            $prepare.IsEnabled=(Test-PreparationAdministrator)
            if (-not $prepare.IsEnabled) { $preview.Text += "`r`n`r`nTo prepare a partition, open Windows PowerShell as administrator and launch this script again." }
        } catch { Show-Error $_.Exception.Message }
    }
})
$window.FindName('Refresh').Add_Click({ Refresh-Drives })
$window.FindName('BuildHP').Add_Click({
    # A separate console keeps the interface responsive and exposes build output.
    $path=Join-Path $PSScriptRoot 'Build-HPExternal.ps1'
    Start-Process powershell.exe -ArgumentList "-NoExit -NoProfile -ExecutionPolicy Bypass -File `"$path`""
})
$save.Add_Click({
    try {
        $fresh=@(Get-InstallInventory | Where-Object { $_.Number -eq $script:plan.Disk.Number })
        if ($fresh.Count -ne 1) { throw 'Drive disappeared. Refresh the list.' }
        $null=Assert-PlanMatchesInventory $script:plan $fresh[0]
        $dialog=New-Object Microsoft.Win32.SaveFileDialog
        $dialog.Filter='JSON plan (*.json)|*.json'; $dialog.FileName='gbrunch-install-plan.json'; $dialog.OverwritePrompt=$true
        if ($dialog.ShowDialog()) { $script:plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $dialog.FileName -Encoding UTF8 }
    } catch { Show-Error $_.Exception.Message }
})
$prepare.Add_Click({
    try {
        $chosen=$script:plan
        $phrase=Get-PreparationPhrase $chosen
        $dialog=New-Object Windows.Window
        $dialog.Title='Confirm partition preparation'; $dialog.Width=650; $dialog.Height=370; $dialog.Owner=$window; $dialog.WindowStartupLocation='CenterOwner'
        $panel=New-Object Windows.Controls.StackPanel; $panel.Margin='20'
        $warning=New-Object Windows.Controls.TextBlock; $warning.TextWrapping='Wrap'
        $warning.Text="Disk $($chosen.Disk.Number): $($chosen.Disk.Model), $($chosen.Disk.BusType)`r`nTarget: $($chosen.Target.Label), $([Math]::Round($chosen.Target.Size / 1GB,2)) GiB`r`n`r`nALL FILES in an existing selected partition will be erased. This only creates NTFS staging, not Googlebook OS. Final installation will replace this filesystem again.`r`n`r`nType exactly: $phrase"
        $panel.Children.Add($warning) | Out-Null
        $inputBox=New-Object Windows.Controls.TextBox; $inputBox.Margin='0,12,0,12'; $panel.Children.Add($inputBox) | Out-Null
        $confirm=New-Object Windows.Controls.Button; $confirm.Content='Erase / prepare selected target'; $confirm.IsEnabled=$false; $panel.Children.Add($confirm) | Out-Null
        $inputBox.Add_TextChanged({ $confirm.IsEnabled=($inputBox.Text -ceq $phrase) }.GetNewClosure())
        $confirm.Add_Click({ $dialog.DialogResult=$true }.GetNewClosure())
        $dialog.Content=$panel
        if ($dialog.ShowDialog() -eq $true) {
            $window.IsEnabled=$false
            try {
                $log=Join-Path $env:LOCALAPPDATA ('GBRUNCH\Preparation\'+[Guid]::NewGuid().ToString())
                $result=Invoke-StagingPreparation -Plan $chosen -Confirmation $inputBox.Text -LogDirectory $log
                Refresh-Drives
                $preview.Text="NTFS staging prepared. It is NOT bootable and does not contain Googlebook OS.`r`nJournal: $($result.Journal)`r`nFinal ext4 deployment will replace this filesystem."
            } finally { $window.IsEnabled=$true }
        }
    } catch { Show-Error $_.Exception.Message }
})
Refresh-Drives
$null=$window.ShowDialog()
