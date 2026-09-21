# F3R2 V5 memory release helper
# Run in an ELEVATED PowerShell window:  powershell -ExecutionPolicy Bypass -File .\FREE_MEMORY_FOR_V5.ps1
$ErrorActionPreference = 'SilentlyContinue'

function Get-AvailableGB {
    $m = Get-Counter '\Memory\Available MBytes' -SampleInterval 1 -MaxSamples 1
    return [math]::Round(($m.CounterSamples[0].CookedValue) / 1024, 3)
}

Write-Host ("AVAILABLE_GB_BEFORE=" + (Get-AvailableGB))

# 1) ASUS ROG Live Service (largest single consumer; needs admin)
Stop-Service -Name 'ROGLiveService' -Force
taskkill /F /PID (Get-Process -Name 'ROGLiveService' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Id) 2>$null

# 2) Background CAE MCP / skill bridge python servers (not needed for the SolidWorks V5 build)
$patterns = @('CAE-Agent-Hub\MCP', 'codex_skill\mcp', 'claude-skills\_bridge', 'comsol_link', 'Aerospace_MCP_Skills', 'qwen_vision')
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" | ForEach-Object {
    $cmd = $_.CommandLine
    foreach ($pat in $patterns) {
        if ($cmd -like "*$pat*") {
            taskkill /F /PID $_.ProcessId 2>$null
            break
        }
    }
}

# 3) Optional non-essential apps (ChatGPT desktop is intentionally kept)
$appNames = @('msedge', 'chrome', 'steam', 'steamwebhelper', 'OneDrive', 'PhoneExperienceHost', 'BackgroundDownload')
foreach ($name in $appNames) {
    taskkill /IM "$name.exe" /F /T 2>$null
}

Start-Sleep -Seconds 3
Write-Host ("AVAILABLE_GB_AFTER=" + (Get-AvailableGB))
Write-Host "DONE_FREE_MEMORY"
