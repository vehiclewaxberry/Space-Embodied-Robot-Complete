$ErrorActionPreference = 'Stop'
$dmRoot = Split-Path -Parent $PSScriptRoot
$dmDest = Join-Path $dmRoot 'sources/motorbridge'
$dmCommit = 'c48ebc4b2f250aa1f411a580d9d7b626e187040f'
$dmPaths = @('LICENSE','Cargo.toml','README.md','motor_core/Cargo.toml','motor_core/src/bus.rs','motor_core/src/model.rs','motor_core/src/dm_serial.rs','motor_core/src/dm_device.rs','motor_core/src/test_support.rs','motor_core/src/error.rs','motor_vendors/damiao/Cargo.toml','motor_vendors/damiao/src/lib.rs','motor_vendors/damiao/src/protocol.rs','motor_vendors/damiao/src/registers.rs','motor_vendors/damiao/src/motor.rs','motor_vendors/damiao/src/controller.rs','bindings/python/src/motorbridge/__init__.py','bindings/python/src/motorbridge/core.py','bindings/python/src/motorbridge/abi.py','bindings/python/src/motorbridge/dm_device_runtime.py','bindings/python/src/motorbridge/errors.py','bindings/python/src/motorbridge/models.py','bindings/python/examples/damiao_dm_serial_demo.py')
$dmRecords = @()
foreach ($dmName in $dmPaths) {
    $dmUrl = "https://raw.githubusercontent.com/motorbridge/motorbridge/$dmCommit/$dmName"
    $dmFile = Join-Path $dmDest $dmName
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $dmFile)) | Out-Null
    if (-not (Test-Path -LiteralPath $dmFile) -or (Get-Item -LiteralPath $dmFile).Length -eq 0) {
        try { Invoke-WebRequest -Uri $dmUrl -OutFile $dmFile -TimeoutSec 40 }
        catch {
            $dmApi = Invoke-RestMethod -Uri "https://api.github.com/repos/motorbridge/motorbridge/contents/${dmName}?ref=$dmCommit"
            [System.IO.File]::WriteAllBytes($dmFile, [Convert]::FromBase64String($dmApi.content))
        }
    }
    $dmRecords += @{upstream_path=$dmName;url=$dmUrl;local_path=$dmFile;bytes=(Get-Item -LiteralPath $dmFile).Length;sha256=(Get-FileHash -LiteralPath $dmFile -Algorithm SHA256).Hash.ToLower()}
}
$dmUrl = 'https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/'
$dmFile = Join-Path $dmDest 'seeed_dm_quick_start.html'
Invoke-WebRequest -Uri $dmUrl -OutFile $dmFile -TimeoutSec 40
$dmRecords += @{url=$dmUrl;local_path=$dmFile;bytes=(Get-Item -LiteralPath $dmFile).Length;sha256=(Get-FileHash -LiteralPath $dmFile -Algorithm SHA256).Hash.ToLower();kind='snapshot_unversioned_official_document'}
[System.IO.Directory]::CreateDirectory((Join-Path $dmRoot 'results')) | Out-Null
$dmResult = @{repository='https://github.com/motorbridge/motorbridge';commit=$dmCommit;license='MIT; see included LICENSE';retrieved_utc=[DateTime]::UtcNow.ToString('o');execution='download only; no upstream imports, gateways or device enumeration';files=$dmRecords}
$dmResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $dmRoot 'results/DM_SOURCE_MANIFEST.json') -Encoding utf8
@{files=$dmRecords.Count;bytes=($dmRecords | Measure-Object bytes -Sum).Sum;commit=$dmCommit} | ConvertTo-Json
