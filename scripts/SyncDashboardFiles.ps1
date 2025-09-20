# Define Source and Destination Folders
$SourceFolder = "C:\Users\Richard Wilks\AppData\Roaming\MetaQuotes\Terminal\F2262CFAFF47C27887389DAB2852351A\MQL4\Include\Dashboard"
$DestinationFolder = "C:\Users\Richard Wilks\AppData\Roaming\MetaQuotes\Terminal\F2262CFAFF47C27887389DAB2852351A\MQL4\Include\ALLDASHBOARDFILES"
$LogFile = "$DestinationFolder\FileList.txt"

# Ensure Destination Folder Exists
If (!(Test-Path -Path $DestinationFolder)) {
    New-Item -ItemType Directory -Path $DestinationFolder -Force
}

# Function to Sync Files and Generate File List
Function Sync-Files {
    # Clear previous log file
    if (Test-Path $LogFile) { Remove-Item $LogFile -Force }

    # Get all files recursively from source folder
    $files = Get-ChildItem -Path $SourceFolder -Recurse -File

    foreach ($file in $files) {
        # Destination path (flattening structure)
        $destFile = Join-Path -Path $DestinationFolder -ChildPath $file.Name

        # Copy file if newer or doesn't exist
        Copy-Item -Path $file.FullName -Destination $destFile -Force

        # Log original path
        "$($file.Name) - $($file.FullName)" | Out-File -Append -FilePath $LogFile
    }

    # Display file list in Notepad
    Start-Process notepad.exe -ArgumentList $LogFile
}

# Run Sync
Sync-Files

# Open the Destination Folder in File Explorer
Start-Process explorer.exe -ArgumentList $DestinationFolder

# Exit PowerShell
exit

