$ShortcutPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "Sync Dashboard Files.lnk")
$TargetPath = "powershell.exe"
$Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"C:\Users\Richard Wilks\Scripts\SyncDashboardFiles.ps1`""
$WScriptShell = New-Object -ComObject -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.Arguments = $Arguments
$Shortcut.WorkingDirectory = "C:\Users\Richard Wilks\Scripts"
$Shortcut.Save()

Write-Host "Shortcut created on Desktop."