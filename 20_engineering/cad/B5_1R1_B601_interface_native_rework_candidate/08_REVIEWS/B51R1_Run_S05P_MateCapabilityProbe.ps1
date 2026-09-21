[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05P'
$carrierDir = Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S05P_MateCapabilityProbe.dll'
$baseCarrier = Join-Path $carrierDir 'B51R1_CARRIER_base_link.SLDPRT'
$link1Carrier = Join-Path $carrierDir 'B51R1_CARRIER_link1.SLDPRT'
$readinessReceipt = Join-Path $sessionRoot 'B51R1_S05P_READINESS_RECEIPT.json'
$inputLock = Join-Path $sessionRoot 'B51R1_S05P_INPUT_LOCK.json'
$probeReceipt = Join-Path $sessionRoot 'B51R1_S05P_MATE_CAPABILITY_RECEIPT.json'
$holdGate = Join-Path $sessionRoot 'B51R1_S05P_ARCHITECTURE_HOLD_GATE.json'
$progress = Join-Path $sessionRoot 'B51R1_S05P_PROGRESS.log'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $Bytes) { throw "$Label byte count mismatch" }
    if ((Get-Sha $Path) -ne $Sha256.ToUpperInvariant()) { throw "$Label SHA-256 mismatch" }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only output exists: $Path" }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 50 -Compress) + [Environment]::NewLine), $utf8)
}

function Write-TextCreateNew([string]$Path, [string]$Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only output exists: $Path" }
    $utf8 = New-Object Text.UTF8Encoding($false)
    $stream = New-Object IO.FileStream($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $writer = New-Object IO.StreamWriter($stream, $utf8)
        try { $writer.Write($Value) } finally { $writer.Dispose() }
    } finally { $stream.Dispose() }
}

$lockedItems = @(
    [ordered]@{id='S04B_GATE';path='07_VERIFICATION/AUTONOMOUS/S04B_R2/B51R1_S04B_R2_ALL_TEN_CARRIER_GATE.json';bytes=6340;sha256='1EDC34BA0E40DA0409DC5041DE0A5C77C75315F77917A8717206C773AE6F8BF7'},
    [ordered]@{id='S05_ACTIVATION';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V19_POOL_A_A08_S05_ACTIVATION.yaml';bytes=585;sha256='0FA4E757240D8C89DF2176C931BA983899E6C81963056B4D129E2C0D9DF4D75D'},
    [ordered]@{id='CARRIER_CONTRACT_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT_V2.md';bytes=2498;sha256='96A54E088A588338059AF902FD69C4B66A79C9E1FAA92A47A66692236D978ED8'},
    [ordered]@{id='BASE_CARRIER';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_base_link.SLDPRT';bytes=48891;sha256='1151ECD78BC18AD9CCBF2B3EC86365879D09B0CCF14425C17A09DD84119F7F62'},
    [ordered]@{id='LINK1_CARRIER';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_link1.SLDPRT';bytes=58153;sha256='1796D153CF9DEDD6618495C463C16FA7E0039CF2DBE5B8961D0E2EA8BDBDE4FB'},
    [ordered]@{id='READINESS_PROBE';path='08_REVIEWS/B51R1_SR03_ExistingSolidWorksProbe.dll';bytes=5632;sha256='DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2'}
)

foreach ($output in @($readinessReceipt, $inputLock, $probeReceipt, $holdGate, $progress)) {
    if (Test-Path -LiteralPath $output) { throw "S05P append-only output already exists: $output" }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw 'S05P requires zero existing SLDWORKS processes before launch'
}
foreach ($item in $lockedItems) {
    Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id)
}
if (-not (Test-Path -LiteralPath $toolDll -PathType Leaf)) { throw 'S05P tool DLL missing' }
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SolidWorks executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SolidWorks interop'

[IO.Directory]::CreateDirectory($sessionRoot) | Out-Null
$launched = $null
$launchedPid = $null
try {
    Write-TextCreateNew $progress ("S05P_START " + [DateTimeOffset]::Now.ToString('o') + [Environment]::NewLine)
    $launched = Start-Process -FilePath $solidworksExe -PassThru
    $deadline = [DateTimeOffset]::Now.AddMinutes(3)
    while ([DateTimeOffset]::Now -lt $deadline -and $null -eq $launchedPid) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $processes[0].Refresh()
        if ($processes[0].Responding -and $processes[0].MainWindowHandle -ne [IntPtr]::Zero) { $launchedPid = $processes[0].Id }
    }
    if ($null -eq $launchedPid) { throw 'Visible responsive SolidWorks process was not ready within three minutes' }
    $quietStart = [DateTimeOffset]::Now
    Start-Sleep -Seconds 60
    $quietEnd = [DateTimeOffset]::Now
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'S05P lost the sole SolidWorks process during zero-COM window' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding) { throw 'S05P SolidWorks process was not stable' }

    Add-Type -Path $interop
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $ready = [B51R1SR03ExistingSolidWorksProbe]::Run($launchedPid, $readinessReceipt)
    if ($ready -ne 0) { throw "S05P readiness probe returned $ready" }
    $readyData = Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt | ConvertFrom-Json
    if ($readyData.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') { throw 'S05P readiness failed' }

    $runtimeItems = @($lockedItems) + @(
        [ordered]@{id='S05P_TOOL';path='08_REVIEWS/B51R1_S05P_MateCapabilityProbe.dll';bytes=(Get-Item $toolDll).Length;sha256=Get-Sha $toolDll},
        [ordered]@{id='READINESS_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S05P/B51R1_S05P_READINESS_RECEIPT.json';bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt}
    )
    $lock = [ordered]@{
        schema='B51R1_S05P_INPUT_LOCK_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
        status='PASS_S05P_INPUTS_HASH_LOCKED';session_id='S05P'
        runtime_boundary=[ordered]@{solidworks_process_id=$launchedPid;process_count=1;document_count=0;zero_com_quiet_window_seconds=($quietEnd-$quietStart).TotalSeconds}
        transaction=[ordered]@{operation='READ_ONLY_J01_MATE_CAPABILITY_PROBE';save3_call_count_allowed=0;save_as_call_count_allowed=0;formal_s05_output_allowed=$false}
        locked_items=$runtimeItems;claim_limit='ARCHITECTURE_CAPABILITY_EVIDENCE_ONLY_NO_S05_G4_OR_T005_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = [B51R1S05PMateCapabilityProbe]::Run($launchedPid, $baseCarrier, $link1Carrier, $probeReceipt)
    if ($result -ne 0) { throw "S05P capability probe returned $result" }
    $probe = Get-Content -Raw -Encoding UTF8 -LiteralPath $probeReceipt | ConvertFrom-Json
    if ($probe.status -ne 'S05P_ARCHITECTURE_HOLD_CONFIRMED' -or $probe.gate_pass -ne $false) {
        throw 'S05P receipt did not confirm the controlled architecture HOLD'
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SolidWorks remains after S05P normal ExitApp' }
    foreach ($item in $lockedItems) {
        Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id)
    }
    $gate = [ordered]@{
        schema='B51R1_S05P_ARCHITECTURE_HOLD_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
        status='S05P_HOLD_CURRENT_CARRIERS_NOT_MATE_READY';gate_pass=$false
        probe_receipt=[ordered]@{path='07_VERIFICATION/AUTONOMOUS/S05P/B51R1_S05P_MATE_CAPABILITY_RECEIPT.json';bytes=(Get-Item $probeReceipt).Length;sha256=Get-Sha $probeReceipt}
        missing_reference_features=@('AXIS_joint1_PARENT_SIDE','PLANE_SEAT_joint1_PARENT_SIDE','PLANE_ZERO_joint1_PARENT_SIDE','PLANE_SEAT_joint1_CHILD_SIDE')
        protected_carriers_unchanged=$true;save3_call_count=0;save_as_call_count=0
        recovery_authorized='VERSIONED_CARRIER_MATE_DATUM_REPAIR_ONLY'
        formal_s05_authorized=$false;t005_authorized=$false
        claim_limit='CURRENT_TOPOLOGY_HOLD_AND_VERSIONED_RECOVERY_AUTHORIZATION_ONLY'
    }
    Write-JsonCreateNew $holdGate $gate
    Add-Content -Encoding UTF8 -LiteralPath $progress -Value ("S05P_HOLD_CONFIRMED " + [DateTimeOffset]::Now.ToString('o'))
    Write-Output $holdGate
}
catch {
    try { Add-Content -Encoding UTF8 -LiteralPath $progress -Value ("S05P_EXCEPTION " + $_.Exception.ToString()) } catch { }
    throw
}
