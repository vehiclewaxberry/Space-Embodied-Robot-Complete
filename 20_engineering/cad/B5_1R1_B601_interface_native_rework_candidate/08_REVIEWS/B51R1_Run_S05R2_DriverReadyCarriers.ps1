[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('PilotCreate','PilotVerify','BatchCreate','AllVerify')]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$inputDir = Join-Path $root '03_CAD\11_MATE_READY_CARRIERS'
$outputDir = Join-Path $root '03_CAD\12_DRIVER_READY_CARRIERS'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S05R2_DriverReadyCarrierTool.dll'

$allParts = @(
    'base_link','link1','link2','link3','link4','link5','link6',
    'gripper_link','gripper_left','gripper_right'
)
$v2Locks = [ordered]@{
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
$pilotMr1Locks = [ordered]@{
    base_link=@(90751,'628B908ADB4593019FB7E6A866320FF9D58DA0AEE55774ED3E67A25191BAD4A3')
    link1=@(89843,'59B54D8F6F5F1E8DAD8DCAF3DFC0AA346B482A19FCE31F66A03D020B15C5D5C5')
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

function Assert-V2Carriers {
    $source = Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS'
    foreach ($link in $allParts) {
        Assert-File (Join-Path $source "B51R1_CARRIER_$link.SLDPRT") ([long]$v2Locks[$link][0]) ([string]$v2Locks[$link][1]) "V2_$link"
    }
}

function Get-ExistingParts([string]$Directory, [string]$Prefix) {
    @($allParts | ForEach-Object {
        $path = Join-Path $Directory "$Prefix$_.SLDPRT"
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            [ordered]@{link=$_;path=$path;bytes=(Get-Item -LiteralPath $path).Length;sha256=Get-Sha $path}
        }
    })
}

function Assert-Snapshot($Snapshot, [string]$Label) {
    foreach ($item in @($Snapshot)) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "$Label`_$($item.link)"
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
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $utf8 = New-Object Text.UTF8Encoding($false)
    $stream = New-Object IO.FileStream($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $writer = New-Object IO.StreamWriter($stream, $utf8)
        try { $writer.Write($Value) } finally { $writer.Dispose() }
    } finally { $stream.Dispose() }
}

function Read-PassGate([string]$RelativePath, [string]$ExpectedStatus) {
    $path = Join-Path $root $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Prerequisite Gate missing: $path" }
    $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json
    if ($data.gate_pass -ne $true -or $data.status -ne $ExpectedStatus) { throw "Prerequisite Gate mismatch: $path" }
    if ($data.PSObject.Properties.Name -contains 'receipt') {
        Assert-File ([string]$data.receipt.path) ([long]$data.receipt.bytes) ([string]$data.receipt.sha256) "RECEIPT_$ExpectedStatus"
    }
    [ordered]@{path=$path;bytes=(Get-Item -LiteralPath $path).Length;sha256=Get-Sha $path;status=$data.status;data=$data}
}

function Assert-GateParts($GateRecord, [string[]]$Links, [string]$Label) {
    $parts = @($GateRecord.data.parts)
    if ($parts.Count -ne $Links.Count) { throw "$Label part count mismatch" }
    foreach ($link in $Links) {
        $matches = @($parts | Where-Object { $_.link -eq $link })
        if ($matches.Count -ne 1) { throw "$Label missing or duplicate part: $link" }
        Assert-File ([string]$matches[0].path) ([long]$matches[0].bytes) ([string]$matches[0].sha256) "$Label`_$link"
    }
}

$modeData = switch ($Mode) {
    'PilotCreate' {
        [ordered]@{
            session='S05R2_P';expectedStatus='S05R2_P_BASE_AND_LINK1_MR2_CREATED';expectedCount=2;expectedSaveAs=2
            targetLinks=@('base_link','link1');receipt='B51R1_S05R2_P_PILOT_CREATE_RECEIPT.json';progress='B51R1_S05R2_P_PROGRESS.log'
            gate='B51R1_S05R2_P_MR2_PILOT_CREATE_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V22R2_POOL_A_A08R2_PC_MR2_PILOT_COLD_REOPEN_ACTIVATION.yaml'
        }
    }
    'PilotVerify' {
        [ordered]@{
            session='S05R2_PC';expectedStatus='S05R2_PC_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS';expectedCount=2;expectedSaveAs=0
            targetLinks=@('base_link','link1');receipt='B51R1_S05R2_PC_PILOT_COLD_REOPEN_RECEIPT.json';progress='B51R1_S05R2_PC_PROGRESS.log'
            gate='B51R1_S05R2_PC_MR2_PILOT_COLD_REOPEN_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V22R3_POOL_A_A08R2_J01_MR2_NATIVE_1R_PILOT_ACTIVATION.yaml'
        }
    }
    'BatchCreate' {
        [ordered]@{
            session='S05R2_B';expectedStatus='S05R2_B_REMAINING_EIGHT_MR2_CREATED';expectedCount=8;expectedSaveAs=8
            targetLinks=@('link2','link3','link4','link5','link6','gripper_link','gripper_left','gripper_right')
            receipt='B51R1_S05R2_B_BATCH_CREATE_RECEIPT.json';progress='B51R1_S05R2_B_PROGRESS.log'
            gate='B51R1_S05R2_B_REMAINING_EIGHT_CREATE_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V23R1_POOL_A_A08R2_BC_ALL_MR2_COLD_REOPEN_ACTIVATION.yaml'
        }
    }
    'AllVerify' {
        [ordered]@{
            session='S05R2_BC';expectedStatus='S05R2_BC_ALL_TEN_MR2_COLD_REOPEN_PASS';expectedCount=10;expectedSaveAs=0
            targetLinks=$allParts;receipt='B51R1_S05R2_BC_ALL_COLD_REOPEN_RECEIPT.json';progress='B51R1_S05R2_BC_PROGRESS.log'
            gate='B51R1_S05R2_BC_ALL_TEN_COLD_REOPEN_GATE.json'
            nextActivation='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V24R1_POOL_A_A08_S05_NATIVE_CHAIN_REACTIVATION_WITH_MR2.yaml'
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
    [ordered]@{id='MR1_TOOL_SOURCE';path='08_REVIEWS/B51R1_S05R_MateReadyCarrierTool.cs';bytes=39550;sha256='A176AE8D4D88A3A02F0C6CAE2DC6D5F64A73BC13493AB5EC6C5BAB4FF2F04795'},
    [ordered]@{id='MR1_TOOL_BINARY';path='08_REVIEWS/B51R1_S05R_MateReadyCarrierTool.dll';bytes=30208;sha256='7BA5B25EE6ECDA16E711C4B583945E4BEBEBC22D583BADC3115DA388DA457C14'},
    [ordered]@{id='MR1_PILOT_COLD_GATE';path='07_VERIFICATION/AUTONOMOUS/S05R_PC/B51R1_S05R_PC_MR1_PILOT_COLD_REOPEN_GATE.json';bytes=1646;sha256='9B38184763A5C9EB5E72292E80184CB7952652BB895CC412D1BC68E2A60DE39A'},
    [ordered]@{id='MR1_DRIVER_HOLD';path='07_VERIFICATION/AUTONOMOUS/S05R_J01_PRECHECK/B51R1_S05R_J01_MR1_DRIVER_REFERENCE_HOLD.json';bytes=1408;sha256='542572A3F8862587316D8C42A0866D8D0E8ECC479073FB52464143A864E08250'},
    [ordered]@{id='CONTRACT_V4';path='03_CAD/12_DRIVER_READY_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md';bytes=2185;sha256='49DBE417CE68792C29C5B1F47454F7FDD86D0CA3B75590EC465DD39051080F77'},
    [ordered]@{id='REGISTER_V4';path='04_CONFIGURATION/B51R1_CARRIER_REGISTER_V4.csv';bytes=1614;sha256='B1EA795A5D8AC7246CE5CC1B85B1E63C42661448636299A908971D712657E1D6'},
    [ordered]@{id='RECOVERY_ACTIVATION_V22R1';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V22R1_POOL_A_A08R2_MR2_DRIVER_REFERENCE_RECOVERY_ACTIVATION.yaml';bytes=829;sha256='8F17D1EBCE8123DDE81FE81CB67D2FD4116BB1D478CF87AF96A8CB00608B36C7'},
    [ordered]@{id='MR2_TOOL_SOURCE';path='08_REVIEWS/B51R1_S05R2_DriverReadyCarrierTool.cs';bytes=53299;sha256='B357F3F6BA5D9F420CDD4AE32F96F65DD417771D17F6F82D127AAB40077ADF50'},
    [ordered]@{id='MR2_TOOL_BINARY';path='08_REVIEWS/B51R1_S05R2_DriverReadyCarrierTool.dll';bytes=43008;sha256='32945766072FF821AF21B0E91512453A3232D793215D18C2888D32653AF81BD4'},
    [ordered]@{id='READINESS_PROBE';path='08_REVIEWS/B51R1_SR03_ExistingSolidWorksProbe.dll';bytes=5632;sha256='DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2'}
)

foreach ($path in @($readinessReceipt,$inputLock,$receipt,$progress,$gate,$nextActivation)) {
    if (Test-Path -LiteralPath $path) { throw "Append-only output already exists: $path" }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw "$Mode requires zero existing SLDWORKS processes" }
foreach ($item in $commonLocks) { Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id) }
Assert-V2Carriers
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SolidWorks executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SolidWorks interop'
foreach ($link in $pilotMr1Locks.Keys) { Assert-File (Join-Path $inputDir "B51R1_CARRIER_MR1_$link.SLDPRT") ([long]$pilotMr1Locks[$link][0]) ([string]$pilotMr1Locks[$link][1]) "MR1_$link" }

$prerequisites = @()
switch ($Mode) {
    'PilotVerify' {
        $record = Read-PassGate '07_VERIFICATION/AUTONOMOUS/S05R2_P/B51R1_S05R2_P_MR2_PILOT_CREATE_GATE.json' 'S05R2_P_BASE_AND_LINK1_MR2_CREATED'
        Assert-GateParts $record @('base_link','link1') 'MR2_PILOT_CREATE'; $prerequisites += $record
    }
    'BatchCreate' {
        $j01 = Read-PassGate '07_VERIFICATION/AUTONOMOUS/S05R2_J01/B51R1_S05R2_J01_NATIVE_1R_GATE.json' 'S05R2_J01_NATIVE_1R_PILOT_PASS'
        $mr1 = Read-PassGate '07_VERIFICATION/AUTONOMOUS/S05R_B/B51R1_S05R_B_REMAINING_EIGHT_CREATE_GATE.json' 'S05R_B_REMAINING_EIGHT_MR1_CREATED'
        Assert-GateParts $mr1 $modeData.targetLinks 'MR1_BATCH_CREATE'; $prerequisites += @($j01,$mr1)
    }
    'AllVerify' {
        $pilot = Read-PassGate '07_VERIFICATION/AUTONOMOUS/S05R2_PC/B51R1_S05R2_PC_MR2_PILOT_COLD_REOPEN_GATE.json' 'S05R2_PC_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS'
        $batch = Read-PassGate '07_VERIFICATION/AUTONOMOUS/S05R2_B/B51R1_S05R2_B_REMAINING_EIGHT_CREATE_GATE.json' 'S05R2_B_REMAINING_EIGHT_MR2_CREATED'
        Assert-GateParts $pilot @('base_link','link1') 'MR2_PILOT_COLD'; Assert-GateParts $batch @('link2','link3','link4','link5','link6','gripper_link','gripper_left','gripper_right') 'MR2_BATCH_CREATE'
        $prerequisites += @($pilot,$batch)
    }
}

foreach ($link in $modeData.targetLinks) {
    $path = Join-Path $outputDir "B51R1_CARRIER_MR2_$link.SLDPRT"
    if ($Mode -in @('PilotCreate','BatchCreate')) {
        if (Test-Path -LiteralPath $path) { throw "Controlled MR2 output exists: $path" }
    } elseif (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required MR2 input missing: $path" }
}

$mr1Before = Get-ExistingParts $inputDir 'B51R1_CARRIER_MR1_'
$mr2Before = Get-ExistingParts $outputDir 'B51R1_CARRIER_MR2_'
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
        if ($processes[0].Responding -and $processes[0].MainWindowHandle -ne [IntPtr]::Zero) { $launchedPid = $processes[0].Id }
    }
    if ($null -eq $launchedPid) { throw 'Visible responsive SolidWorks process was not ready within three minutes' }
    $quietStart = [DateTimeOffset]::Now
    Start-Sleep -Seconds 30
    $quietEnd = [DateTimeOffset]::Now
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'MR2 session lost the sole SolidWorks process' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding) { throw 'MR2 process was not stable' }

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
        transaction=[ordered]@{save_mr1_source_allowed=$false;save3_call_count_allowed=0;save_as_call_count_allowed=$modeData.expectedSaveAs;transform2_allowed=$false;formal_s05_output_allowed=$false}
        locked_items=$commonLocks;v2_carrier_hashes=$v2Locks;mr1_inputs_before=$mr1Before;mr2_inputs_before=$mr2Before;prerequisite_gates=$prerequisites
        readiness_receipt=[ordered]@{path=$readinessReceipt;bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt}
        claim_limit='VERSIONED_DRIVER_REFERENCE_RECOVERY_ONLY_NO_S05_G4_OR_T005_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = switch ($Mode) {
        'PilotCreate' { [B51R1S05R2DriverReadyCarrierTool]::CreatePilot($launchedPid,$inputDir,$outputDir,$receipt,$progress) }
        'PilotVerify' { [B51R1S05R2DriverReadyCarrierTool]::VerifyPilot($launchedPid,$outputDir,$receipt,$progress) }
        'BatchCreate' { [B51R1S05R2DriverReadyCarrierTool]::CreateRemaining($launchedPid,$inputDir,$outputDir,$receipt,$progress) }
        'AllVerify' { [B51R1S05R2DriverReadyCarrierTool]::VerifyAll($launchedPid,$outputDir,$receipt,$progress) }
    }
    if ($result -ne 0) { throw "$Mode tool returned $result" }
    $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($data.status -ne $modeData.expectedStatus) { throw "$Mode status mismatch: $($data.status)" }
    $observedCount = if ($Mode -in @('PilotCreate','BatchCreate')) { $data.created_part_count } else { $data.verified_part_count }
    if ($observedCount -ne $modeData.expectedCount -or $data.save3_call_count -ne 0 -or $data.save_as_call_count -ne $modeData.expectedSaveAs) { throw "$Mode count/save contract mismatch" }
    if ($data.normal_document_close -ne $true -or $data.final_document_count -ne 0 -or $data.normal_application_exit -ne $true) { throw "$Mode normal-close contract mismatch" }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SolidWorks remains after normal ExitApp' }

    Assert-V2Carriers; Assert-Snapshot $mr1Before 'MR1_PROTECTED'
    foreach ($item in $commonLocks) { Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id) }
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
        checks=[ordered]@{protected_v2_carriers_unchanged=$true;protected_mr1_carriers_unchanged=$true;full_inherited_datum_inventory_exact=$true;driver_reference_geometry_exact=$true;zero_bodies=$true;zero_cad_mass=$true;zero_external_references=$true;normal_document_close=$true;normal_application_exit=$true}
        formal_s05_authorized=$false;t005_authorized=$false
        claim_limit='DRIVER_READY_CARRIER_RECOVERY_GATE_ONLY_NO_S05_G4_OR_T005_CREDIT'
    }
    if ($Mode -eq 'PilotCreate') { $gateData['pilot_cold_reopen_authorized']=$true }
    if ($Mode -eq 'PilotVerify') { $gateData['j01_mr2_native_1r_pilot_authorized']=$true }
    if ($Mode -eq 'BatchCreate') { $gateData['all_ten_mr2_cold_reopen_authorized']=$true }
    if ($Mode -eq 'AllVerify') { $gateData['formal_s05_reactivation_authorized']=$true }
    Write-JsonCreateNew $gate $gateData

    $activation = switch ($Mode) {
        'PilotCreate' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V22R2_POOL_A_A08R2_PC_MR2_PILOT_COLD_REOPEN_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: S05R2_PC_MR2_PILOT_COLD_REOPEN_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R2_P/B51R1_S05R2_P_MR2_PILOT_CREATE_GATE.json
scope: READ_ONLY_BASE_LINK_AND_LINK1_MR2
save_api_call_count_allowed: 0
formal_s05_output_allowed: false
t005_authorized: false
"@ }
        'PilotVerify' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V22R3_POOL_A_A08R2_J01_MR2_NATIVE_1R_PILOT_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: S05R2_J01_NATIVE_1R_PILOT_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R2_PC/B51R1_S05R2_PC_MR2_PILOT_COLD_REOPEN_GATE.json
output: 03_CAD/20_NATIVE_ASSEMBLY/PILOT/B51R1_CARRIER_J01_NATIVE_PILOT.SLDASM
scope: J00_ROOT_AND_J01_MR2_NATIVE_1R_ONLY
formal_s05_output_allowed: false
t005_authorized: false
"@ }
        'BatchCreate' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V23R1_POOL_A_A08R2_BC_ALL_MR2_COLD_REOPEN_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: S05R2_BC_ALL_TEN_MR2_COLD_REOPEN_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R2_B/B51R1_S05R2_B_REMAINING_EIGHT_CREATE_GATE.json
scope: READ_ONLY_ALL_TEN_MR2
save_api_call_count_allowed: 0
formal_s05_output_allowed: false
t005_authorized: false
"@ }
        'AllVerify' { @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V24R1_POOL_A_A08_S05_NATIVE_CHAIN_REACTIVATION_WITH_MR2
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: POOL_A_A08_S05_NATIVE_CARRIER_CHAIN_REACTIVATED_WITH_MR2
activation_gate: 07_VERIFICATION/AUTONOMOUS/S05R2_BC/B51R1_S05R2_BC_ALL_TEN_COLD_REOPEN_GATE.json
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
