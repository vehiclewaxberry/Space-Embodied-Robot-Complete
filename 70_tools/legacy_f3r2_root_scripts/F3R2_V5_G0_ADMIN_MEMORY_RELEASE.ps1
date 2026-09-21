#Requires -RunAsAdministrator

$ErrorActionPreference = 'Continue'

# Temporary G0 resource release only. This script does not change service
# startup types and does not delete or modify project files.
$serviceNames = @(
    'MSSQL$SQLEXPRESS',
    'MSSQLFDLauncher$SQLEXPRESS',
    'MSSQLLaunchpad$SQLEXPRESS',
    'SQLPBDMS$SQLEXPRESS',
    'SQLPBENGINE$SQLEXPRESS',
    'SQLTELEMETRY$SQLEXPRESS',
    'SQLWriter',
    'Aura Wallpaper Service',
    'ROG Live Service',
    'ArmouryCrateService',
    'NvContainerLocalSystem'
)

$results = foreach ($name in $serviceNames) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        [pscustomobject]@{ Name = $name; Before = 'NOT_FOUND'; After = 'NOT_FOUND'; Error = '' }
        continue
    }

    $before = $service.Status.ToString()
    $errorMessage = ''
    if ($service.Status -ne 'Stopped') {
        try {
            Stop-Service -Name $name -Force -ErrorAction Stop
        }
        catch {
            $errorMessage = $_.Exception.Message
        }
    }
    $after = (Get-Service -Name $name -ErrorAction SilentlyContinue).Status.ToString()
    [pscustomobject]@{ Name = $name; Before = $before; After = $after; Error = $errorMessage }
}

$processNames = @(
    'NVIDIA Overlay',
    'Aura Wallpaper Service',
    'AuraWallpaperService',
    'ROGLiveService',
    'asus_framework',
    'AcPowerNotification',
    'AMDRSSrcExt'
)

Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $processNames -contains $_.ProcessName } |
    Stop-Process -Force -ErrorAction SilentlyContinue

$results | Format-Table -AutoSize

Start-Sleep -Seconds 3
1..5 | ForEach-Object {
    $os = Get-CimInstance Win32_OperatingSystem
    [pscustomobject]@{
        Sample = $_
        Timestamp = (Get-Date).ToString('o')
        AvailableGiB = [math]::Round(($os.FreePhysicalMemory * 1KB / 1GB), 6)
    }
    if ($_ -lt 5) { Start-Sleep -Seconds 1 }
} | Format-Table -AutoSize

