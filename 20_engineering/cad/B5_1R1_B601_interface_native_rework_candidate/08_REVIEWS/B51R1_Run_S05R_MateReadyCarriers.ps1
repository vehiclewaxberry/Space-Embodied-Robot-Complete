[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('PilotCreate','PilotVerify','BatchCreate','AllVerify')]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sourceDir = Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS'
$outputDir = Join-Path $root '03_CAD\11_MATE_READY_CARRIERS'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S05R_MateReadyCarrierTool.dll'

$allParts = @(
    'base_link','link1','link2','link3','link4','link5','link6',
    'gripper_link','gripper_left','gripper_right'
)
$sourceLocks = [ordered]@{
    base_link=@(48891,'1151ECD78BC18AD9CCBF2B3EC86365879D09B0CCF14425C17A09DD84119F7F62')
    link1=@(58153,'1796D153CF9DEDD6618495C463C16FA7E0039CF2DBE5B8961D0E2EA8BDBDE4FB')
    link2=@(54727,'39FA03DECA9DF2AE567008DD8DD04D61F625FE356D8A27B388285F8AB5AF7BAC')
    link3=@(55076,'B3DA4072D13DECB83F102682D8F5E0A28662D217B50AAC56BCA6E9A761A98CD6')
    link4=@(57089,'99EF2480F93AFF513B7CFED04DEAC87D0C0F909771A8CD749A011642C5647732')
    link5=@(58995,'C052B4BBAAD8A1B11FAA9A96729B92247A731498BCD198F750F295501F17A792')
    link6=@(56126,'C4017087690FEED642A964492E3D23B6CFFE9736BA3D57ED2D5D3A61A20E2FD5')
    gripper_link=@(52289,'2911B6D241C8C12BBF5CFD0D4AEF2CD46F782DD75A9B06192126724B7BC4209E')
    gripper_left=@(57123,'94BB24EBF9B0C58E69C4BA93C27F336167284A4EA49E614577C03D965920FD39')
    gripper_right=@(57973,'DB4E93DC07271675F5FC2E494191E4DFD97262A53D09D0EBCACD40C7085114DB')
}

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $Bytes) { throw "$Label byte count mismatch: $($item.Length) != $Bytes" }
    if ((Get-Sha $Path) -ne $Sha256.ToUpperInvariant()) { throw "$Label SHA-256 mismatch" }
}

function Assert-SourceCarriers {
    foreach ($link in $allParts) {
        $path = Join-Path $sourceDir "B51R1_CARRIER_$link.SLDPRT"
        Assert-File $path ([long]$sourceLocks[$link][0]) ([string]$sourceLocks[$link][1]) "SOURCE_$link"
    }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only output exists: $Path" }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 80 -Compress) + [Environment]::NewLine), $utf8)
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

$modeData = switch ($Mode) {
    'PilotCreate' {
        [ordered]@{
            session='S05R_P'; expectedStatus='S05R_P_BASE_AND_LINK1_MR1_CREATED'
            expectedCount=2; expectedSaveAs=2; targetLinks=@('base_link','link1')
            receipt='B51R1_S05R_P_PILOT_CREATE_RECEIPT.json'; progress='B51R1_S05R_P_PROGRESS.log'
            gate='B51R1_S05R_P_MR1_PILOT_CREATE_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V21_POOL_A_A08R_PC_MR1_PILOT_COLD_REOPEN_ACTIVATION.yaml'
        }
    }
    'PilotVerify' {
        [ordered]@{
            session='S05R_PC'; expectedStatus='S05R_PC_BASE_AND_LINK1_MR1_COLD_REOPEN_PASS'
            expectedCount=2; expectedSaveAs=0; targetLinks=@('base_link','link1')
            receipt='B51R1_S05R_PC_PILOT_COLD_REOPEN_RECEIPT.json'; progress='B51R1_S05R_PC_PROGRESS.log'
            gate='B51R1_S05R_PC_MR1_PILOT_COLD_REOPEN_GATE.json'
            prerequisite='07_VERIFICATION/AUTONOMOUS/S05R_P/B51R1_S05R_P_MR1_PILOT_CREATE_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V22_POOL_A_A08R_J01_NATIVE_1R_PILOT_ACTIVATION.yaml'
        }
    }
    'BatchCreate' {
        [ordered]@{
            session='S05R_B'; expectedStatus='S05R_B_REMAINING_EIGHT_MR1_CREATED'
            expectedCount=8; expectedSaveAs=8; targetLinks=@('link2','link3','link4','link5','link6','gripper_link','gripper_left','gripper_right')
            receipt='B51R1_S05R_B_BATCH_CREATE_RECEIPT.json'; progress='B51R1_S05R_B_PROGRESS.log'
            gate='B51R1_S05R_B_REMAINING_EIGHT_CREATE_GATE.json'
            prerequisite='07_VERIFICATION/AUTONOMOUS/S05R_J01/B51R1_S05R_J01_NATIVE_1R_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V23_POOL_A_A08R_BC_ALL_MR1_COLD_REOPEN_ACTIVATION.yaml'
        }
    }
    'AllVerify' {
        [ordered]@{
            session='S05R_BC'; expectedStatus='S05R_BC_ALL_TEN_MR1_COLD_REOPEN_PASS'
            expectedCount=10; expectedSaveAs=0; targetLinks=$allParts
            receipt='B51R1_S05R_BC_ALL_COLD_REOPEN_RECEIPT.json'; progress='B51R1_S05R_BC_PROGRESS.log'
            gate='B51R1_S05R_BC_ALL_TEN_COLD_REOPEN_GATE.json'
            prerequisite='07_VERIFICATION/AUTONOMOUS/S05R_B/B51R1_S05R_B_REMAINING_EIGHT_CREATE_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V24_POOL_A_A08_S05_NATIVE_CHAIN_REACTIVATION.yaml'
        }
    }
}

$sessionRoot = Join-Path $root "07_VERIFICATION\AUTONOMOUS\$($modeData.session)"
$readinessReceipt = Join-Path $sessionRoot "B51R1_$($modeData.session)_READINESS_RECEIPT.json"
$inputLock = Join-Path $sessionRoot "B51R1_$($modeData.session)_INPUT_LOCK.json"
$receipt = Join-Path $sessionRoot $modeData.receipt
$progress = Join-Path $sessionRoot $modeData.progress
$gate = Join-Path $sessionRoot $modeData.gate
$nextActivation = Join-Path $root $modeData.nextActivation

$commonLocks = @(
    [ordered]@{id='S05P_HOLD';path='07_VERIFICATION/AUTONOMOUS/S05P/B51R1_S05P_ARCHITECTURE_HOLD_GATE.json';bytes=792;sha256='9DC5237FB2703C13DD72A5E72B8F8CB09E1ED541671A2DD75282F1ED7D6D747E'},
    [ordered]@{id='CONTRACT_V3';path='03_CAD/11_MATE_READY_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT_V3.md';bytes=3818;sha256='437D060351C4B995BF42AC8EC7FD39A9FDB03CDD9269AC94C5DAC268AB43051B'},
    [ordered]@{id='REGISTER_V3';path='04_CONFIGURATION/B51R1_CARRIER_REGISTER_V3.csv';bytes=2866;sha256='3FB83FDDE48DDBBDEA0EE544E6173BC0B738FD9EC28C0DEBD30326296198A7D1'},
    [ordered]@{id='RECOVERY_ACTIVATION_V20';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V20_POOL_A_A08R_S05_MATE_DATUM_RECOVERY_ACTIVATION.yaml';bytes=1037;sha256='EA071935DFB6959EEC5829C2FDB16653FAACD389C0CFCC3A37AC8D319B9B9AB5'},
    [ordered]@{id='RECOVERY_TOOL_SOURCE';path='08_REVIEWS/B51R1_S05R_MateReadyCarrierTool.cs';bytes=39550;sha256='A176AE8D4D88A3A02F0C6CAE2DC6D5F64A73BC13493AB5EC6C5BAB4FF2F04795'},
    [ordered]@{id='RECOVERY_TOOL_BINARY';path='08_REVIEWS/B51R1_S05R_MateReadyCarrierTool.dll';bytes=30208;sha256='7BA5B25EE6ECDA16E711C4B583945E4BEBEBC22D583BADC3115DA388DA457C14'},
    [ordered]@{id='READINESS_PROBE';path='08_REVIEWS/B51R1_SR03_ExistingSolidWorksProbe.dll';bytes=5632;sha256='DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2'}
)

foreach ($output in @($readinessReceipt,$inputLock,$receipt,$progress,$gate,$nextActivation)) {
    if (Test-Path -LiteralPath $output) { throw "Append-only output already exists: $output" }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "$Mode requires zero existing SLDWORKS processes"
}
foreach ($item in $commonLocks) {
    Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id)
}
Assert-SourceCarriers
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SolidWorks executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SolidWorks interop'

if ($modeData.Contains('prerequisite')) {
    $prerequisite = Join-Path $root ([string]$modeData.prerequisite)
    if (-not (Test-Path -LiteralPath $prerequisite -PathType Leaf)) { throw "Prerequisite Gate missing: $prerequisite" }
    $prerequisiteData = Get-Content -Raw -Encoding UTF8 -LiteralPath $prerequisite | ConvertFrom-Json
    if ($prerequisiteData.PSObject.Properties.Name -contains 'gate_pass') {
        if ($prerequisiteData.gate_pass -ne $true) { throw "Prerequisite Gate is not PASS: $prerequisite" }
    }
    if ($prerequisiteData.PSObject.Properties.Name -contains 'parts') {
        foreach ($part in @($prerequisiteData.parts)) {
            Assert-File ([string]$part.path) ([long]$part.bytes) ([string]$part.sha256) "PREREQUISITE_MR1_$($part.link)"
        }
    }
}

$currentMr1 = @()
foreach ($link in $allParts) {
    $path = Join-Path $outputDir "B51R1_CARRIER_MR1_$link.SLDPRT"
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $currentMr1 += [ordered]@{link=$link;path=$path;bytes=(Get-Item $path).Length;sha256=Get-Sha $path}
    }
}
if ($Mode -in @('PilotCreate','BatchCreate')) {
    foreach ($link in $modeData.targetLinks) {
        $path = Join-Path $outputDir "B51R1_CARRIER_MR1_$link.SLDPRT"
        if (Test-Path -LiteralPath $path) { throw "Controlled MR1 output exists: $path" }
    }
}
if ($Mode -in @('PilotVerify','AllVerify')) {
    foreach ($link in $modeData.targetLinks) {
        $path = Join-Path $outputDir "B51R1_CARRIER_MR1_$link.SLDPRT"
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "MR1 input missing: $path" }
    }
}

[IO.Directory]::CreateDirectory($sessionRoot) | Out-Null
$launched = $null
$launchedPid = $null
try {
    $launched = Start-Process -FilePath $solidworksExe -PassThru
    $deadline = [DateTimeOffset]::Now.AddMinutes(3)
    while ([DateTimeOffset]::Now -lt $deadline -and $null -eq $launchedPid) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $processes[0].Refresh()
        if ($processes[0].Responding -and $processes[0].MainWindowHandle -ne [IntPtr]::Zero) {
            $launchedPid = $processes[0].Id
        }
    }
    if ($null -eq $launchedPid) { throw 'Visible responsive SolidWorks process was not ready within three minutes' }
    $quietStart = [DateTimeOffset]::Now
    Start-Sleep -Seconds 60
    $quietEnd = [DateTimeOffset]::Now
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'Recovery session lost the sole SolidWorks process' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding) { throw 'Recovery process was not stable' }

    Add-Type -Path $interop
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $ready = [B51R1SR03ExistingSolidWorksProbe]::Run($launchedPid,$readinessReceipt)
    if ($ready -ne 0) { throw "Readiness probe returned $ready" }
    $readyData = Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt | ConvertFrom-Json
    if ($readyData.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') { throw 'Readiness did not pass' }

    $lock = [ordered]@{
        schema="B51R1_$($modeData.session)_INPUT_LOCK_V1";generated_at=[DateTimeOffset]::Now.ToString('o')
        status="PASS_$($modeData.session)_INPUTS_HASH_LOCKED";session_id=$modeData.session;mode=$Mode
        runtime_boundary=[ordered]@{solidworks_process_id=$launchedPid;process_count=1;document_count=0;zero_com_quiet_window_seconds=($quietEnd-$quietStart).TotalSeconds}
        transaction=[ordered]@{save_source_carrier_allowed=$false;save3_call_count_allowed=0;save_as_call_count_allowed=$modeData.expectedSaveAs;transform2_allowed=$false;formal_s05_output_allowed=$false}
        locked_items=$commonLocks;source_carrier_hashes=$sourceLocks;mr1_inputs_before=$currentMr1
        readiness_receipt=[ordered]@{path=$readinessReceipt;bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt}
        claim_limit='VERSIONED_MATE_DATUM_RECOVERY_ONLY_NO_S05_G4_OR_T005_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = switch ($Mode) {
        'PilotCreate' { [B51R1S05RMateReadyCarrierTool]::CreatePilot($launchedPid,$sourceDir,$outputDir,$receipt,$progress) }
        'PilotVerify' { [B51R1S05RMateReadyCarrierTool]::VerifyPilot($launchedPid,$outputDir,$receipt,$progress) }
        'BatchCreate' { [B51R1S05RMateReadyCarrierTool]::CreateRemaining($launchedPid,$sourceDir,$outputDir,$receipt,$progress) }
        'AllVerify' { [B51R1S05RMateReadyCarrierTool]::VerifyAll($launchedPid,$outputDir,$receipt,$progress) }
    }
    if ($result -ne 0) { throw "$Mode tool returned $result" }
    $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($data.status -ne $modeData.expectedStatus) { throw "$Mode status mismatch: $($data.status)" }
    $observedCount = if ($Mode -in @('PilotCreate','BatchCreate')) { $data.created_part_count } else { $data.verified_part_count }
    if ($observedCount -ne $modeData.expectedCount -or $data.save3_call_count -ne 0 -or $data.save_as_call_count -ne $modeData.expectedSaveAs) {
        throw "$Mode count/save contract mismatch"
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SolidWorks remains after normal ExitApp' }
    Assert-SourceCarriers
    foreach ($item in $commonLocks) {
        Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id)
    }

    $partEvidence = @($data.parts | ForEach-Object {
        $sha = if ($_.PSObject.Properties.Name -contains 'output_sha256') { $_.output_sha256 } else { $_.sha256_before_after }
        $path = if ($_.PSObject.Properties.Name -contains 'output_path') { $_.output_path } else { $_.path }
        [ordered]@{link=$_.link;path=$path;bytes=(Get-Item -LiteralPath $path).Length;sha256=$sha;feature_count=$_.feature_count;body_count=$_.body_count;external_reference_count=$_.external_reference_count}
    })
    $gateData = [ordered]@{
        schema="B51R1_$($modeData.session)_GATE_V1";generated_at=[DateTimeOffset]::Now.ToString('o')
        status=$modeData.expectedStatus;gate_pass=$true;mode=$Mode
        receipt=[ordered]@{path=$receipt;bytes=(Get-Item $receipt).Length;sha256=Get-Sha $receipt}
        parts=$partEvidence;part_count=$partEvidence.Count
        checks=[ordered]@{protected_v2_carriers_unchanged=$true;zero_bodies=$true;zero_cad_mass=$true;zero_external_references=$true;native_ref_features_exact=$true;normal_application_exit=$true}
        formal_s05_authorized=$false;t005_authorized=$false
        claim_limit='MATE_READY_CARRIER_RECOVERY_GATE_ONLY_NO_S05_G4_OR_T005_CREDIT'
    }
    if ($Mode -eq 'PilotCreate') { $gateData['pilot_cold_reopen_authorized']=$true }
    if ($Mode -eq 'PilotVerify') { $gateData['j01_native_1r_pilot_authorized']=$true }
    if ($Mode -eq 'BatchCreate') { $gateData['all_ten_cold_reopen_authorized']=$true }
    if ($Mode -eq 'AllVerify') { $gateData['formal_s05_reactivation_authorized']=$true }
    Write-JsonCreateNew $gate $gateData

    $activation = switch ($Mode) {
        'PilotCreate' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V21_POOL_A_A08R_PC_MR1_PILOT_COLD_REOPEN_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: S05R_PC_MR1_PILOT_COLD_REOPEN_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R_P/B51R1_S05R_P_MR1_PILOT_CREATE_GATE.json
scope: READ_ONLY_BASE_LINK_AND_LINK1_MR1
save_api_call_count_allowed: 0
formal_s05_output_allowed: false
t005_authorized: false
"@ }
        'PilotVerify' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V22_POOL_A_A08R_J01_NATIVE_1R_PILOT_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: S05R_J01_NATIVE_1R_PILOT_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R_PC/B51R1_S05R_PC_MR1_PILOT_COLD_REOPEN_GATE.json
output: 03_CAD/20_NATIVE_ASSEMBLY/PILOT/B51R1_CARRIER_J01_NATIVE_PILOT.SLDASM
scope: J00_ROOT_AND_J01_NATIVE_1R_ONLY
formal_s05_output_allowed: false
t005_authorized: false
"@ }
        'BatchCreate' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V23_POOL_A_A08R_BC_ALL_MR1_COLD_REOPEN_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: S05R_BC_ALL_TEN_MR1_COLD_REOPEN_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R_B/B51R1_S05R_B_REMAINING_EIGHT_CREATE_GATE.json
scope: READ_ONLY_ALL_TEN_MR1
save_api_call_count_allowed: 0
formal_s05_output_allowed: false
t005_authorized: false
"@ }
        'AllVerify' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V24_POOL_A_A08_S05_NATIVE_CHAIN_REACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: POOL_A_A08_S05_NATIVE_CARRIER_CHAIN_REACTIVATED_WITH_MR1
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R_BC/B51R1_S05R_BC_ALL_TEN_COLD_REOPEN_GATE.json
output: 03_CAD/20_NATIVE_ASSEMBLY/B51R1_CARRIER_CHAIN_NATIVE.SLDASM
joint_sequence: J00-J09
required_topology: 6R+1_FIXED+2_INDEPENDENT_P
t005_authorized: false
"@ }
    }
    Write-TextCreateNew $nextActivation $activation
    Write-Output $gate
}
catch {
    throw
}
