# Windows PowerShell 5.1 / WPF front end. Preview only: no deployment engine.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run this interface on Windows.' }
if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') { throw 'Start with powershell.exe -STA -File windows\Start-Installer.ps1' }
Import-Module (Join-Path $PSScriptRoot 'InstallPlan.psm1') -Force
. (Join-Path $PSScriptRoot 'Get-InstallInventory.ps1')
Add-Type -AssemblyName PresentationFramework
[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="GBRUNCH - Windows installer preview" Width="1000" Height="760" MinWidth="800" MinHeight="650" WindowStartupLocation="CenterScreen">
 <Grid Margin="20"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="180"/><RowDefinition Height="*"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
 <TextBlock Text="Experimental Windows installer - target selection preview" FontSize="23" FontWeight="Bold" TextWrapping="Wrap"/>
 <TextBlock Grid.Row="1" Margin="0,12" TextWrapping="Wrap" Text="Experimental software: installation can erase data or leave a machine unable to boot. This preview makes no disk or boot changes. Internal drives and external USB SSDs can be inspected. Installation is disabled until the new boot layout is validated."/>
 <DockPanel Grid.Row="2" Margin="0,0,0,10"><Button Name="Refresh" DockPanel.Dock="Right" Content="Refresh drives" Padding="12,6"/><ComboBox Name="Drives" DisplayMemberPath="Display" Margin="0,0,10,0"/></DockPanel>
 <DataGrid Name="Targets" Grid.Row="3" IsReadOnly="True" AutoGenerateColumns="False" SelectionMode="Single" SelectionUnit="FullRow" CanUserAddRows="False">
 <DataGrid.Columns><DataGridTextColumn Header="Target" Binding="{Binding Label}" Width="2*"/><DataGridTextColumn Header="Size (GiB)" Binding="{Binding GiB}" Width="90"/><DataGridCheckBoxColumn Header="Eligible" Binding="{Binding Eligible}" Width="70"/><DataGridTextColumn Header="Protection / reason" Binding="{Binding Reason}" Width="3*"/></DataGrid.Columns></DataGrid>
 <TextBox Name="Preview" Grid.Row="4" Margin="0,12" IsReadOnly="True" TextWrapping="Wrap" VerticalScrollBarVisibility="Auto" Text="Select a drive, then a partition or unallocated extent. No target is selected automatically."/>
 <StackPanel Grid.Row="5" Orientation="Horizontal" HorizontalAlignment="Right"><Button Name="Save" Content="Save plan..." IsEnabled="False" Padding="14,8" Margin="0,0,12,0"/><Button Content="Install - not yet available" IsEnabled="False" Padding="14,8"/></StackPanel>
 </Grid>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load((New-Object Xml.XmlNodeReader $xaml))
$drives=$window.FindName('Drives'); $targets=$window.FindName('Targets'); $preview=$window.FindName('Preview'); $save=$window.FindName('Save')
$script:plan = $null
function Show-Error($err) { $preview.Text = "Unable to continue: $err"; $save.IsEnabled=$false; $script:plan=$null }
function Refresh-Drives {
    $save.IsEnabled=$false; $script:plan=$null; $targets.ItemsSource=$null; $drives.ItemsSource=$null
    try {
        $script:inventory=@(Get-InstallInventory)
        $rows=@($script:inventory | ForEach-Object { [pscustomobject]@{ Display="Disk $($_.Number) | $($_.Model) | $([Math]::Round($_.Size / 1GB,1)) GiB | $($_.BusType) | $($_.PartitionStyle)"; Disk=$_ } })
        $drives.ItemsSource=$rows; $drives.SelectedIndex=-1
        $preview.Text='Choose a drive by model, size and connection. Disk numbers can change after reconnecting. C: free space is not unallocated space; this preview never shrinks Windows.'
    } catch { Show-Error $_.Exception.Message }
}
$drives.Add_SelectionChanged({
    $save.IsEnabled=$false; $script:plan=$null; $targets.ItemsSource=$null
    if ($drives.SelectedItem) {
        try { $targets.ItemsSource=@(Get-TargetChoices $drives.SelectedItem.Disk | ForEach-Object { $_ | Add-Member -NotePropertyName GiB -NotePropertyValue ([Math]::Round($_.Size / 1GB,2)) -PassThru }); $targets.SelectedIndex=-1; $preview.Text='Choose a target. Replacing a partition erases all files in that partition. Protected rows cannot be used.' } catch { Show-Error $_.Exception.Message }
    }
})
$targets.Add_SelectionChanged({
    $save.IsEnabled=$false; $script:plan=$null
    if ($targets.SelectedItem -and $drives.SelectedItem) {
        try {
            $script:plan=New-InstallPlan $drives.SelectedItem.Disk $targets.SelectedItem
            $warning=if ($script:plan.ErasesSelectedPartition) {'WOULD ERASE the selected partition and every file in it.'} else {'Would create one partition inside the selected unallocated extent.'}
            $preview.Text="$warning`r`n`r`n" + ($script:plan | ConvertTo-Json -Depth 8)
            $save.IsEnabled=$true
        } catch { Show-Error $_.Exception.Message }
    }
})
$window.FindName('Refresh').Add_Click({ Refresh-Drives })
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
Refresh-Drives
$null=$window.ShowDialog()
